"""Tests for benchmark/tools/_release.py: both manifest layouts, and the model check.

  python -m unittest discover -s benchmark/tests

Set MTG_RELEASE_DIR to a downloaded release directory (manifest.json and
items.jsonl.gz beside mtgdataset.urna) to also read a real release.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from _release import check_items, check_model_identity, load_build_manifest  # noqa: E402

ITEMS = [{"key": f"k{i}", "label": f"card {i}", "ordinal": i} for i in range(3)]
MODELS = {"siglip2": {"model_hash": "sha256:aa"}}
SPACES = [{"name": "siglip2", "dim": None, "modality": "image", "preset": "siglip2"}]


def refuses(fn, *args):
    try:
        fn(*args)
    except SystemExit as e:
        return e.code == 2
    return False


class LoadBuildManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.index = self.tmp / "mtgdataset.urna"
        self.index.write_bytes(b"")

    def test_candidate_layout_with_embedded_items(self):
        (self.tmp / "mtgdataset.manifest.json").write_text(json.dumps({"items": ITEMS, "models": MODELS}))
        self.assertEqual(load_build_manifest(self.index)["items"], ITEMS)

    def test_release_layout_with_stripped_items(self):
        (self.tmp / "manifest.json").write_text(json.dumps({"items": {"stripped_to": "items.jsonl.gz", "n": 3}}))
        with gzip.open(self.tmp / "items.jsonl.gz", "wt") as f:
            f.writelines(json.dumps(it) + "\n" for it in ITEMS)
        self.assertEqual(load_build_manifest(self.index)["items"], ITEMS)

    def test_release_layout_with_a_wrong_count_is_refused(self):
        (self.tmp / "manifest.json").write_text(json.dumps({"items": {"stripped_to": "items.jsonl.gz", "n": 4}}))
        with gzip.open(self.tmp / "items.jsonl.gz", "wt") as f:
            f.writelines(json.dumps(it) + "\n" for it in ITEMS)
        self.assertTrue(refuses(load_build_manifest, self.index))

    def test_missing_items_file_and_missing_manifest_are_refused(self):
        self.assertTrue(refuses(load_build_manifest, self.index))
        (self.tmp / "manifest.json").write_text(json.dumps({"items": {"stripped_to": "items.jsonl.gz", "n": 3}}))
        self.assertTrue(refuses(load_build_manifest, self.index))

    @unittest.skipUnless(os.environ.get("MTG_RELEASE_DIR"), "MTG_RELEASE_DIR not set")
    def test_a_real_release(self):
        rel = Path(os.environ["MTG_RELEASE_DIR"])
        m = load_build_manifest(rel / "mtgdataset.urna")
        self.assertEqual(len(m["items"]), 38627)
        self.assertEqual([it["ordinal"] for it in m["items"]], list(range(38627)))


class RealFile(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("MTG_RELEASE_DIR"), "MTG_RELEASE_DIR not set")
    def test_the_release_model_matches_its_file(self):
        try:
            import urna
        except ImportError:
            self.skipTest("the urna library is not installed")
        rel = Path(os.environ["MTG_RELEASE_DIR"])
        if not (rel / "mtgdataset.urna").is_file():
            self.skipTest("the release dir has no mtgdataset.urna")
        m = load_build_manifest(rel / "mtgdataset.urna")
        info = urna.open(str(rel / "mtgdataset.urna")).inspect()
        spaces = [s for s in m["spaces"] if s["modality"] == "image"]
        for s in spaces:
            want = m["models"][s["preset"]]["model_hash"]
            dim = next(fs["dim"] for fs in info["spaces"] if fs["name"] == s["name"])
            check_model_identity(s["preset"], want, dim, m, info["spaces"], [s])
            self.assertTrue(
                refuses(check_model_identity, s["preset"], "sha256:" + "0" * 64, dim, m, info["spaces"], [s])
            )


class CheckModelIdentity(unittest.TestCase):
    def file_spaces(self, model_hash="sha256:aa", dim=768):
        return [{"name": "siglip2", "model_hash": model_hash, "dim": dim}]

    def test_the_built_model_passes(self):
        check_model_identity("siglip2", "sha256:aa", 768, {"models": MODELS}, self.file_spaces(), SPACES)

    def test_another_snapshot_is_refused(self):
        self.assertTrue(
            refuses(check_model_identity, "siglip2", "sha256:bb", 768, {"models": MODELS}, self.file_spaces(), SPACES)
        )

    def test_a_space_built_with_another_model_is_refused(self):
        self.assertTrue(
            refuses(
                check_model_identity,
                "siglip2",
                "sha256:aa",
                768,
                {"models": MODELS},
                self.file_spaces("sha256:cc"),
                SPACES,
            )
        )

    def test_dims_must_fit(self):
        sliced = [dict(SPACES[0], dim=256)]
        check_model_identity("siglip2", "sha256:aa", 768, {"models": MODELS}, self.file_spaces(dim=256), sliced)
        self.assertTrue(
            refuses(
                check_model_identity, "siglip2", "sha256:aa", 128, {"models": MODELS}, self.file_spaces(dim=256), sliced
            )
        )
        self.assertTrue(
            refuses(
                check_model_identity, "siglip2", "sha256:aa", 768, {"models": MODELS}, self.file_spaces(dim=512), sliced
            )
        )

    def test_a_file_space_without_hash_or_dim_is_refused(self):
        no_hash = [{"name": "siglip2", "dim": 768}]
        no_dim = [{"name": "siglip2", "model_hash": "sha256:aa"}]
        self.assertTrue(refuses(check_model_identity, "siglip2", "sha256:aa", 768, {"models": MODELS}, no_hash, SPACES))
        self.assertTrue(refuses(check_model_identity, "siglip2", "sha256:aa", 768, {"models": MODELS}, no_dim, SPACES))

    def test_a_manifest_without_the_preset_is_refused(self):
        self.assertTrue(
            refuses(check_model_identity, "wemm-2b", "sha256:aa", 768, {"models": MODELS}, self.file_spaces(), SPACES)
        )


class CheckItems(unittest.TestCase):
    def test_items_that_match_the_file_pass(self):
        check_items(ITEMS, 3, ["a", "b", "c"])

    def test_a_count_that_differs_is_refused(self):
        self.assertTrue(refuses(check_items, ITEMS, 4, ["a", "b", "c", "d"]))
        self.assertTrue(refuses(check_items, ITEMS, 3, ["a", "b"]))

    def test_broken_ordinals_or_keys_are_refused(self):
        gap = [dict(it, ordinal=it["ordinal"] * 2) for it in ITEMS]
        dup = [dict(it, key="k0") for it in ITEMS]
        self.assertTrue(refuses(check_items, gap, 3, ["a", "b", "c"]))
        self.assertTrue(refuses(check_items, dup, 3, ["a", "b", "c"]))


if __name__ == "__main__":
    unittest.main()
