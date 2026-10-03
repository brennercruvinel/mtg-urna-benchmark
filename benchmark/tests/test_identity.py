"""Tests for the identity check of render_report.py, against the records this repo tracks.

python -m unittest discover -s benchmark/tests
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import render_report as rr  # noqa: E402

RJ = rr.env.EXPERIMENTS / "20-full-corpus-utility" / "results.json"
VALID = json.loads(RJ.read_text())["identity"]
RECORDS = rr._records()
ZERO = "sha256:" + "0" * 64


def refused(ident) -> bool:
    try:
        rr.check_identity(RJ, ident, RECORDS)
    except SystemExit as e:
        return e.code == 2
    return False


class Identity(unittest.TestCase):
    def changed(self, fn):
        ident = copy.deepcopy(VALID)
        fn(ident)
        return ident

    def test_every_tracked_result_passes(self):
        for d, doc in rr.experiments():
            self.assertIn("identity", doc, d.name)

    def test_the_valid_block_passes(self):
        self.assertFalse(refused(VALID))

    def test_an_altered_content_hash_is_refused(self):
        self.assertTrue(refused(self.changed(lambda i: i["files"][0].update(content_hash=ZERO))))

    def test_an_altered_file_hash_is_refused(self):
        self.assertTrue(refused(self.changed(lambda i: i["files"][0].update(file_hash=ZERO))))

    def test_an_altered_source_hash_is_refused(self):
        self.assertTrue(refused(self.changed(lambda i: i["source"].update(corpus_input_hash=ZERO))))

    def test_an_altered_model_hash_is_refused(self):
        self.assertTrue(refused(self.changed(lambda i: i["models"][0].update(model_hash=ZERO))))

    def test_a_release_that_does_not_exist_is_refused(self):
        self.assertTrue(refused(self.changed(lambda i: i["files"][0].update(path="release/v9.9/none/mtgdataset.urna"))))

    def test_a_query_list_that_does_not_exist_is_refused(self):
        self.assertTrue(
            refused(self.changed(lambda i: i.update(queries={"n": 5, "list": "benchmark/corpora/none.json"})))
        )

    def test_a_source_list_that_does_not_exist_is_refused(self):
        self.assertTrue(refused(self.changed(lambda i: i["source"].update(list="benchmark/corpora/none.json"))))

    def test_unrecorded_history_is_accepted(self):
        self.assertFalse(
            refused(
                {
                    "source": {"corpus": "sample-2048"},
                    "queries": None,
                    "models": [],
                    "files": [],
                    "unrecorded": "the build was local",
                }
            )
        )

    def test_no_files_and_no_reason_is_refused(self):
        self.assertTrue(refused({"source": {"corpus": "x"}, "queries": None, "models": [], "files": []}))


if __name__ == "__main__":
    unittest.main()
