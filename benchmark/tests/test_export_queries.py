"""Tests for benchmark/tools/export_queries.py on a synthetic card order.

python -m unittest discover -s benchmark/tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import export_queries as eq  # noqa: E402

LABELS = ["Kor Outfitter", "Siren Lookout", "Fireball // Fireball", "Fire // Ice"]
ITEMS = [{"ordinal": i, "key": f"k{i}|o{i}", "label": label} for i, label in enumerate(LABELS)]


class Tables(unittest.TestCase):
    def setUp(self):
        self.corpora = Path(tempfile.mkdtemp())
        for name, keys in (
            ("queries-100", ["k2|o2", "k0|o0"]),
            ("queries-1000", ["k1|o1"]),
            ("queries-200", ["k3|o3"]),
        ):
            (self.corpora / f"{name}.json").write_text(json.dumps({"name": name, "ids": keys}))

    def test_one_relevant_row_per_query_the_card_itself(self):
        queries, qrels = eq.tables(ITEMS, self.corpora)
        self.assertEqual(len(queries), len(qrels))
        for q, r in zip(queries, qrels, strict=True):
            self.assertEqual((q["query_id"], q["key"], q["ordinal"]), (r["query_id"], r["key"], r["ordinal"]))
            self.assertEqual(r["relevance"], 1)
            self.assertEqual(q["text"], f"artwork of the card {q['label']}")

    def test_lists_experiments_and_galleries(self):
        queries, _ = eq.tables(ITEMS, self.corpora)
        by_list = {}
        for q in queries:
            by_list.setdefault(q["list"], []).append(q)
        self.assertEqual([q["key"] for q in by_list["queries-100"]], ["k2|o2", "k0|o0"])
        self.assertEqual(len(by_list["all"]), len(ITEMS))
        self.assertEqual(by_list["queries-200"][0]["gallery"], "sample-512")
        self.assertEqual(by_list["all"][0]["experiment"], "20-full-corpus-utility")

    def test_art_series_is_a_repeated_face_only(self):
        self.assertTrue(eq.art_series("Fireball // Fireball"))
        self.assertFalse(eq.art_series("Fire // Ice"))
        self.assertFalse(eq.art_series("Kor Outfitter"))

    def test_a_list_key_outside_the_card_order_is_refused(self):
        (self.corpora / "queries-1000.json").write_text(json.dumps({"ids": ["nope|x"]}))
        with self.assertRaises(SystemExit):
            eq.tables(ITEMS, self.corpora)


if __name__ == "__main__":
    unittest.main()
