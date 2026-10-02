"""Tests for benchmark/tools/prepare_from_hub.py on a two-row snapshot in the hub's schema.

  python -m unittest discover -s benchmark/tests

The real run (38,627 rows from the hub) is recorded in the pull request and in
docs/changelog.md; these tests cover the refusals and the order of the writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_from_hub as pfh  # noqa: E402


def rows():
    out = []
    for i, (img, oracle, name) in enumerate([("0aa1", "o1", "Kor Outfitter"), ("0bb2", "o2", "Siren Lookout")]):
        data = f"jpeg bytes {i}".encode()
        out.append(
            {
                "ordinal": i, "key": f"{img}|{oracle}", "oracle_id": oracle, "img_id": img, "name": name,
                "pt_name": "Nome" if i == 0 else None, "mana_cost": "{W}", "type_line": "Creature", "rarity": "common",
                "set_code": "zen", "oracle_text": "text", "art_series": False,
                "image_sha256": hashlib.sha256(data).hexdigest(), "image_bytes": len(data),
                "image": {"bytes": data, "path": f"{img}.jpg"},
            }
        )
    return out


class PrepareFromHub(unittest.TestCase):
    def setUp(self):
        import pyarrow as pa
        import pyarrow.parquet as pq

        self.tmp = Path(tempfile.mkdtemp())
        self.shard = self.tmp / "cards-00000-of-00001.parquet"
        pq.write_table(pa.Table.from_pylist(rows()), self.shard)
        self.root = self.tmp / "data"
        self._saved = (pfh.SOURCES, pfh.shards, os.environ.get("MTG_DATA"))
        pfh.shards = lambda pin, cache: [self.shard]
        os.environ["MTG_DATA"] = str(self.root)
        sys.argv = ["prepare_from_hub.py", "--keep-parquet"]

    def tearDown(self):
        pfh.SOURCES, pfh.shards, mtg = self._saved
        if mtg is None:
            os.environ.pop("MTG_DATA", None)
        else:
            os.environ["MTG_DATA"] = mtg

    def pin(self, corpus_input_hash: str) -> None:
        toml = self.tmp / "sources.toml"
        toml.write_text(
            f'[snapshot]\nrepo = "x"\nrevision = "y"\nfiles = "*.parquet"\nrows = 2\nprofile = "stills.toml"\n'
            f'corpus_input_hash = "{corpus_input_hash}"\n'
        )
        pfh.SOURCES = toml

    def run_main(self) -> int:
        try:
            return pfh.main()
        except SystemExit as e:
            return e.code

    def test_a_wrong_input_hash_leaves_no_prepared_json(self):
        self.pin("sha256:" + "0" * 64)
        self.assertEqual(self.run_main(), 2)
        self.assertFalse((self.root / "prepared.json").exists())

    def test_the_matching_hash_writes_prepared_json_last(self):
        import contextlib
        import io

        template, label_tpl, chunker = pfh.profile_recipe(pfh.env.PROFILES / "stills.toml")
        h = hashlib.sha256()
        for r in rows():
            label = label_tpl.format_map(pfh._Blank(r)).strip()
            h.update(pfh.item_input_hash(pfh.render_template(template, r), r["image_sha256"], label, chunker).encode())
        want = "sha256:" + h.hexdigest()
        self.pin(want)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.run_main(), 0)
        prepared = json.loads((self.root / "prepared.json").read_text())
        self.assertEqual(prepared["corpus_input_hash"], want)
        self.assertTrue(prepared["matches_release"])
        self.assertEqual(len(list((self.root / "images").rglob("*.jpg"))), 2)

    def test_a_non_empty_root_is_refused_before_any_write(self):
        self.root.mkdir(parents=True)
        (self.root / "mtg.sqlite").write_text("keep me")
        self.pin("sha256:" + "0" * 64)
        self.assertEqual(self.run_main(), 2)
        self.assertEqual((self.root / "mtg.sqlite").read_text(), "keep me")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["mtg.sqlite"])

    def test_a_scan_that_does_not_match_its_hash_is_refused(self):
        import pyarrow as pa
        import pyarrow.parquet as pq

        bad = rows()
        bad[1]["image_sha256"] = "f" * 64
        pq.write_table(pa.Table.from_pylist(bad), self.shard)
        self.pin("sha256:" + "0" * 64)
        self.assertEqual(self.run_main(), 2)
        self.assertFalse((self.root / "prepared.json").exists())


if __name__ == "__main__":
    unittest.main()
