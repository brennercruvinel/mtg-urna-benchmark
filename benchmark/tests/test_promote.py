"""Tests for benchmark/tools/promote.py: where built_with comes from, and what check refuses.

  python -m unittest discover -s benchmark/tests

Set MTG_RELEASE_DIR to a downloaded release directory (and URNA_BIN or `urna` on
the path) to also check a real release.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import promote  # noqa: E402

A = "sha256:" + "a" * 64
B = "sha256:" + "b" * 64


def refuses(fn, *args):
    try:
        fn(*args)
    except SystemExit as e:
        return e.code == 2
    return False


class ResolveBuiltWith(unittest.TestCase):
    def setUp(self):
        self.key = Path(tempfile.mkdtemp()) / "CITATION_KEY"

    def write_key(self, file_hash):
        self.key.write_text(f"content_hash = {A}\nfile_hash = {file_hash}\nbuilt_with = urna 0.3.0\n")

    def test_kept_for_the_same_file(self):
        self.write_key(A)
        self.assertEqual(promote.resolve_built_with(self.key, A, None), "urna 0.3.0")

    def test_a_disagreeing_flag_for_the_same_file_is_refused(self):
        self.write_key(A)
        self.assertTrue(refuses(promote.resolve_built_with, self.key, A, "urna 0.5.1"))

    def test_another_file_needs_the_flag(self):
        self.write_key(B)
        self.assertTrue(refuses(promote.resolve_built_with, self.key, A, None))
        self.assertEqual(promote.resolve_built_with(self.key, A, "urna 0.5.1"), "urna 0.5.1")

    def test_no_key_needs_the_flag(self):
        self.assertTrue(refuses(promote.resolve_built_with, self.key, A, None))
        self.assertEqual(promote.resolve_built_with(self.key, A, "urna 0.5.1"), "urna 0.5.1")


class Check(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_an_empty_sums_file_is_refused(self):
        (self.dir / "SHA256SUMS").write_text("")
        self.assertFalse(promote.check(self.dir))

    def test_a_manifest_alone_is_refused(self):
        (self.dir / "manifest.json").write_text("{}")
        self.assertFalse(promote.check(self.dir))

    def test_sums_that_list_only_some_files_are_refused(self):
        for name in ("build.lock.json", "manifest.json", "items.jsonl.gz", "CITATION_KEY"):
            (self.dir / name).write_text(name)
        (self.dir / "SHA256SUMS").write_text(f"{promote.sha256(self.dir / 'manifest.json')}  manifest.json\n")
        self.assertFalse(promote.check(self.dir))

    @unittest.skipUnless(os.environ.get("MTG_RELEASE_DIR"), "MTG_RELEASE_DIR not set")
    def test_a_real_release_passes_and_a_tampered_copy_does_not(self):
        rel = Path(os.environ["MTG_RELEASE_DIR"])
        self.assertTrue(promote.check(rel))
        copy = self.dir / "copy"
        copy.mkdir()
        for f in rel.iterdir():
            if f.name == "mtgdataset.urna":
                os.link(f, copy / f.name)
            elif f.is_file():
                shutil.copy2(f, copy / f.name)
        with (copy / "manifest.json").open("a") as fh:
            fh.write(" ")
        self.assertFalse(promote.check(copy))


if __name__ == "__main__":
    unittest.main()
