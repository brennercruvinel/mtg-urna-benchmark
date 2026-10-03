"""Tests for benchmark/tools/export_corpora.py on a synthetic 38627-key card order.

  python -m unittest discover -s benchmark/tests

The real check (the tracked lists against the pinned hub order) runs in CI as
`export_corpora.py --check`; these cover the validation, the refusals and the
all-or-none write without any data.
"""

from __future__ import annotations

import contextlib
import copy
import gzip
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import export_corpora as ec  # noqa: E402

KEYS = sorted(f"{i:06x}img|oracle{i}" for i in range(ec.N_FULL))
KH = ec.keys_hash(KEYS)


def lists() -> list[dict]:
    out = []
    for name, (ids, ords) in ec.derive(KEYS).items():
        extra = {"ordinals": ords} if ords is not None else {}
        out.append(ec.doc(name, 7 if ords else None, "rule", "synthetic", ids, keys_hash=KH, **extra))
    gate_ords = [0, 9, 858]
    out.append(ec.doc("gate-48", None, "rule", "synthetic", [KEYS[o] for o in gate_ords], keys_hash=KH, ordinals=gate_ords))
    out.append(ec.doc("reprints-2787", None, "rule", "synthetic", sorted(["a|1", "b|2"]), groups=1))
    return out


def by_name(name: str) -> dict:
    return copy.deepcopy(next(d for d in lists() if d["name"] == name))


class Problems(unittest.TestCase):
    def test_sound_lists_pass(self):
        for d in lists():
            self.assertEqual(ec.problems(d, KEYS, KH), [], d["name"])

    def test_a_changed_id_is_refused(self):
        d = by_name("queries-100")
        d["ids"][3] = KEYS[0] if d["ids"][3] != KEYS[0] else KEYS[1]
        self.assertTrue(ec.problems(d, KEYS, KH))

    def test_a_repeated_id_and_a_wrong_n_are_refused(self):
        d = by_name("sample-1500")
        d["ids"][1] = d["ids"][0]
        self.assertIn("ids repeat", ec.problems(d, KEYS, KH))
        d = by_name("sample-1500")
        d["n"] = 1499
        self.assertTrue(any(p.startswith("n is") for p in ec.problems(d, KEYS, KH)))

    def test_another_card_order_is_refused(self):
        d = by_name("sample-2048")
        d["keys_hash"] = "sha256:" + "0" * 64
        self.assertTrue(any("keys_hash" in p for p in ec.problems(d, KEYS, KH)))

    def test_ordinals_that_point_elsewhere_are_refused(self):
        d = by_name("frames-96")
        d["ordinals"][0] += 1
        self.assertTrue(any("sample-2048" in p for p in ec.problems(d, KEYS, KH)))
        d = by_name("gate-48")
        d["ordinals"][0] = ec.N_FULL
        self.assertTrue(any("ordinals" in p for p in ec.problems(d, KEYS, KH)))

    def test_reprints_is_checked_without_the_card_order(self):
        d = by_name("reprints-2787")
        self.assertEqual(ec.problems(d, KEYS, KH), [])
        d["ids"] = list(reversed(d["ids"]))
        self.assertIn("ids are not sorted", ec.problems(d, KEYS, KH))


class Check(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "corpora"
        self.items = self.tmp / "items.jsonl.gz"
        with gzip.open(self.items, "wt") as f:
            for i, k in enumerate(KEYS):
                f.write(json.dumps({"ordinal": i, "key": k}) + "\n")
        self._pin = ec.snapshot_pin
        ec.snapshot_pin = lambda: {"keys_hash": KH, "repo": "x", "revision": "y"}
        with contextlib.redirect_stdout(io.StringIO()):
            ec.write_all(lists(), self.out)

    def tearDown(self):
        ec.snapshot_pin = self._pin

    def run_check(self) -> int:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return ec.check(self.out, self.items)
        except SystemExit as e:
            return e.code

    def test_tracked_lists_that_match_pass(self):
        self.assertEqual(self.run_check(), 0)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), sorted(f"{d['name']}.json" for d in lists()))

    def test_a_tampered_file_fails(self):
        p = self.out / "queries-100.json"
        d = json.loads(p.read_text())
        d["ids"][0], d["ids"][1] = d["ids"][1], d["ids"][0]
        p.write_text(json.dumps(d))
        self.assertEqual(self.run_check(), 2)

    def test_a_missing_list_fails(self):
        (self.out / "gate-48.json").unlink()
        self.assertEqual(self.run_check(), 2)

    def test_an_order_that_is_not_the_pin_fails(self):
        ec.snapshot_pin = lambda: {"keys_hash": "sha256:" + "0" * 64, "repo": "x", "revision": "y"}
        self.assertEqual(self.run_check(), 2)


if __name__ == "__main__":
    unittest.main()
