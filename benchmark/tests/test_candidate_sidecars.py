"""Tests for benchmark/tools/candidate_sidecars.py and the candidate layout of promote.py check.

  python -m unittest discover -s benchmark/tests

The real run (five hub candidates, crf50's items byte-equal to the retrieval
release's once decompressed) is recorded in the pull request and the changelog;
these cover the pure parts and the refusals without urna or the files.
"""

from __future__ import annotations

import contextlib
import gzip
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import candidate_sidecars as cs  # noqa: E402
import promote  # noqa: E402

ROWS = [
    {"image_path": f"${{MTG_DATA}}/x/{i}.jpg", "key": f"k{i}|o{i}", "label": f"card {i}", "ordinal": i}
    for i in range(3)
]
URIS = [f"media://mtgdataset-av1.mp4#frame={i}" for i in range(3)]
A = "sha256:" + "a" * 64


def refuses(fn, *args):
    try:
        fn(*args)
    except SystemExit as e:
        return e.code == 2
    return False


class Items(unittest.TestCase):
    def test_equal_rows_give_equal_bytes_in_the_release_line_form(self):
        a, b = cs.items_bytes(ROWS, URIS), cs.items_bytes(ROWS, URIS)
        self.assertEqual(a, b)
        lines = gzip.decompress(a).decode().splitlines()
        self.assertEqual(json.loads(lines[1]), dict(ROWS[1], media_uri=URIS[1]))
        self.assertEqual(lines[0], json.dumps(dict(ROWS[0], media_uri=URIS[0]), sort_keys=True))

    def test_a_uri_list_of_another_length_is_refused(self):
        with self.assertRaises(ValueError):
            cs.items_bytes(ROWS, URIS[:2])


class Manifest(unittest.TestCase):
    def test_the_old_note_becomes_the_release_entry(self):
        old = {"corpus_input_hash": A, "items_stripped": {"n_items": 3, "note": "regenerate with nest build"}}
        new = cs.normalized_manifest(old, 3)
        self.assertNotIn("items_stripped", new)
        self.assertEqual(new["items"], {"fields": cs.FIELDS, "n": 3, "stripped_to": "items.jsonl.gz"})
        self.assertEqual(new["corpus_input_hash"], A)

    def test_a_manifest_already_in_the_release_form_is_left_alone(self):
        m = {"items": {"fields": cs.FIELDS, "n": 3, "stripped_to": "items.jsonl.gz"}}
        self.assertIsNone(cs.normalized_manifest(m, 3))

    def test_a_manifest_with_neither_form_is_refused(self):
        self.assertTrue(refuses(cs.normalized_manifest, {"corpus_input_hash": A}, 3))


class BuiltWith(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "v0.3" / "retrieval").mkdir(parents=True)
        (self.root / "v0.3" / "retrieval" / "CITATION_KEY").write_text(f"file_hash = {A}\nbuilt_with = nest 0.3.0\n")

    def test_a_release_file_with_the_same_hash_gives_its_version(self):
        self.assertEqual(cs.built_with_for(A, None, self.root), "nest 0.3.0")

    def test_another_file_is_unrecorded_unless_given(self):
        other = "sha256:" + "b" * 64
        self.assertEqual(cs.built_with_for(other, None, self.root), "unrecorded")
        self.assertEqual(cs.built_with_for(other, "nest 0.3.0", self.root), "nest 0.3.0")

    def test_the_key_has_the_release_fields(self):
        info = {
            "content_hash": A,
            "file_hash": A,
            "n_chunks": 3,
            "manifest": {"chunker_version": "mtgdataset/1", "title": "t"},
        }
        key = cs.citation_key(info, "unrecorded")
        self.assertEqual(
            [line.split(" = ")[0] for line in key.splitlines()], [*promote.KEY_FIELDS, "built_with", "read_with"]
        )


class CandidateCheck(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def quiet(self, fn, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            return fn(*args), out.getvalue()

    def test_a_candidate_is_held_to_the_forge_names(self):
        (self.dir / "mtgdataset.manifest.json").write_text("{}")
        ok, out = self.quiet(promote.check, self.dir)
        self.assertFalse(ok)
        self.assertIn("missing mtgdataset.build.lock.json", out)
        self.assertNotIn("missing manifest.json", out)

    def test_check_tracked_passes_matching_files_and_refuses_an_edit(self):
        (self.dir / "manifest.json").write_text('{"a": 1}\n')
        (self.dir / "CITATION_KEY").write_text("x\n")
        (self.dir / "SHA256SUMS").write_text(
            f"{promote.sha256(self.dir / 'manifest.json')}  manifest.json\n{'0' * 64}  mtgdataset.urna\n"
        )
        self.assertTrue(self.quiet(promote.check_tracked, self.dir)[0])
        (self.dir / "manifest.json").write_text('{"a": 2}\n')
        self.assertFalse(self.quiet(promote.check_tracked, self.dir)[0])

    def test_check_tracked_needs_the_sums_and_the_key(self):
        self.assertFalse(self.quiet(promote.check_tracked, self.dir)[0])


if __name__ == "__main__":
    unittest.main()
