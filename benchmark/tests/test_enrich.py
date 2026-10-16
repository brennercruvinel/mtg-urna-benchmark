"""Tests for benchmark/tools/enrich.py: the pure functions that turn a parquet row and
its scryfall records into one chunk_scalars row.

  python -m unittest discover -s benchmark/tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import enrich  # noqa: E402

ROW = {
    "ordinal": 0,
    "oracle_id": "o1",
    "name": "Lightning Bolt",
    "pt_name": "Raio",
    "mana_cost": "{R}",
    "type_line": "Instant",
    "rarity": "uncommon",
    "set_code": "lea",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
    "art_series": False,
}
ORACLE = {
    "oracle_id": "o1",
    "colors": ["R"],
    "color_identity": ["R"],
    "cmc": 1.0,
    "keywords": [],
    "layout": "normal",
    "legalities": {"pauper": "legal", "modern": "legal", "standard": "not_legal"},
    "edhrec_rank": 157,
    "games": ["paper"],
    "artist": "Christopher Rush",
    "released_at": "1993-08-05",
    "illustration_id": "i1",
    "reserved": False,
}


class CardRow(unittest.TestCase):
    def test_joins_every_bulk_by_its_key(self):
        prints = {
            "o1": {
                "artists": {"Christopher Rush", "Anato Finnstark"},
                "printings": 2,
                "first": "1993-08-05",
                "last": "2023-01-01",
                "usd": 0.71,
                "langs": {"en", "pt"},
                "pt": ("2023-01-01", "Raio\nMágica Instantânea\nRaio causa 3 pontos de dano"),
            }
        }
        row = enrich.card_row(
            ROW, ORACLE, {"o1": ["Any target means..."]}, {"o1": ["burn any"]}, {"i1": ["lightning"]}, prints
        )
        self.assertEqual(row["kind"], "card")
        self.assertEqual(row["legal"], {"pauper": "legal", "modern": "legal"})
        self.assertEqual(row["rulings"], "Any target means...")
        self.assertEqual(row["tags"], ["burn any"])
        self.assertEqual(row["art_tags"], ["lightning"])
        self.assertEqual(row["artists"], ["Anato Finnstark", "Christopher Rush"])
        self.assertEqual(row["languages"], ["en", "pt"])
        self.assertTrue(row["pt_text"].startswith("Raio"))
        self.assertEqual(row["price_usd"], 0.71)

    def test_kinds_and_faces(self):
        self.assertEqual(enrich.kind({**ROW, "art_series": True}, ORACLE), "art_series")
        self.assertEqual(enrich.kind({**ROW, "type_line": "Token Creature"}, ORACLE), "token")
        self.assertEqual(enrich.kind({**ROW, "name": "A-Bolt"}, None), "alchemy")
        unsanctioned = {**ORACLE, "legalities": {"vintage": "not_legal"}}
        self.assertEqual(enrich.kind(ROW, unsanctioned), "unsanctioned")
        two_faced = {"card_faces": [{"power": "2", "toughness": "2"}, {"power": "4", "toughness": "4"}]}
        self.assertEqual(enrich.face_field(two_faced, "power"), "2 // 4")
        self.assertIsNone(enrich.face_field(two_faced, "loyalty"))
        bare = enrich.card_row(ROW, None, {}, {}, {}, {})
        self.assertEqual(bare["kind"], "card")
        self.assertIsNone(bare["rulings"])
        self.assertNotIn("colors", bare)


if __name__ == "__main__":
    unittest.main()
