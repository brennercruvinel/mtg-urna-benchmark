#!/usr/bin/env python3
"""rows for the card corpus's chunk_scalars, from the parquet snapshot and scryfall.

one row per chunk ordinal: the snapshot's own columns (data/cards-*.parquet)
joined by oracle_id to scryfall's bulks: oracle-cards (colors, mana value,
stats, legality, keywords, popularity, the default printing's artist and date),
rulings (the official rulings text), oracle-tags (the tagger's functional
tags), art-tags (the illustration's tags) and, when present, all-cards (every
printing: artists, printings, first and last release, lowest usd price, the
languages it was printed in, and the portuguese printed text). the output is
zstd json bound to a .urna by its content_hash: the rows `urna scalars` writes
into the file with scalars/schema.json.

  python3 benchmark/tools/enrich.py --parquet DIR --bulks DIR --urna FILE --out rows.json.zst

DIR of --parquet holds cards-*.parquet (the hub snapshot pinned in
sources/sources.toml); DIR of --bulks holds the decompressed jsonl bulks
fetch_bulks.sh leaves. `urna` on PATH or URNA_BIN reads the content_hash.
bulks.json beside --out records each bulk's sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import zstandard

PARQUET_COLUMNS = [
    "ordinal",
    "oracle_id",
    "name",
    "pt_name",
    "mana_cost",
    "type_line",
    "rarity",
    "set_code",
    "oracle_text",
    "art_series",
]
BULKS = ("oracle_cards", "rulings", "oracle_tags", "art_tags", "all_cards")
WEIGHT = {"very_strong": 0, "strong": 1, "median": 2, "weak": 3, "very_weak": 4}


def jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def oracle_index(path: Path) -> dict[str, dict]:
    """oracle_id -> card, faces included (reversible cards keep theirs there)."""
    out: dict[str, dict] = {}
    for c in jsonl(path):
        ids = {c.get("oracle_id")} | {f.get("oracle_id") for f in c.get("card_faces") or []}
        for i in ids - {None}:
            out.setdefault(i, c)
    return out


def rulings_index(path: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for r in jsonl(path):
        out[r["oracle_id"]].append(r["comment"])
    return out


def tag_index(path: Path, key: str) -> dict[str, list[str]]:
    """id (oracle_id or illustration_id) -> the tag labels, strongest first."""
    pairs: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for t in jsonl(path):
        for g in t.get("taggings") or []:
            if g.get(key):
                pairs[g[key]].append((WEIGHT.get(g.get("weight"), 2), t["label"]))
    return {k: [label for _, label in sorted(v)] for k, v in pairs.items()}


def _printed(c: dict) -> str:
    faces = c.get("card_faces") or [c]
    return "\n//\n".join(
        "\n".join(s for s in (f.get("printed_name"), f.get("printed_type_line"), f.get("printed_text")) if s)
        for f in faces
    )


def printings_index(path: Path) -> dict[str, dict]:
    """oracle_id -> what every printing adds: artists, counts, dates, lowest
    price, languages and the portuguese printed text of the latest printing."""
    agg: dict[str, dict] = {}
    for c in jsonl(path):
        oid = c.get("oracle_id") or next(
            (f.get("oracle_id") for f in c.get("card_faces") or [] if f.get("oracle_id")), None
        )
        if not oid:
            continue
        a = agg.setdefault(
            oid,
            {"artists": set(), "printings": 0, "first": None, "last": None, "usd": None, "langs": set(), "pt": None},
        )
        lang = c.get("lang") or "en"
        a["langs"].add(lang)
        if lang == "en":
            a["printings"] += 1
            if c.get("artist"):
                a["artists"].add(c["artist"])
            d = c.get("released_at")
            if d:
                a["first"] = d if a["first"] is None else min(a["first"], d)
                a["last"] = d if a["last"] is None else max(a["last"], d)
            usd = (c.get("prices") or {}).get("usd")
            if usd:
                try:
                    v = float(usd)
                    a["usd"] = v if a["usd"] is None else min(a["usd"], v)
                except ValueError:
                    pass
        if lang == "pt":
            text = _printed(c)
            if text and (a["pt"] is None or (c.get("released_at") or "") > a["pt"][0]):
                a["pt"] = (c.get("released_at") or "", text)
    return agg


def kind(row: dict, sf: dict | None) -> str:
    if row["art_series"]:
        return "art_series"
    t = row["type_line"] or ""
    if "Emblem" in t:
        return "emblem"
    if "Token" in t:
        return "token"
    if sf is None and (row["name"] or "").startswith("A-"):
        return "alchemy"
    if sf is not None and not any(v != "not_legal" for v in (sf.get("legalities") or {}).values()):
        return "unsanctioned"
    return "card"


def face_field(sf: dict, key: str):
    """power, toughness and loyalty live on the faces of a two-faced card."""
    if key in sf:
        return sf[key]
    vals = [f[key] for f in sf.get("card_faces") or [] if key in f]
    return " // ".join(vals) if vals else None


def card_row(row: dict, sf: dict | None, rulings: dict, otags: dict, atags: dict, prints: dict) -> dict:
    out = {
        "ordinal": row["ordinal"],
        "oracle_id": row["oracle_id"],
        "name": row["name"],
        "pt_name": row["pt_name"] or None,
        "mana_cost": row["mana_cost"] or "",
        "type_line": row["type_line"] or "",
        "rarity": row["rarity"] or "",
        "set_code": row["set_code"] or "",
        "kind": kind(row, sf),
        "rulings": "\n".join(rulings.get(row["oracle_id"], [])) or None,
        "tags": otags.get(row["oracle_id"], []),
    }
    if sf is not None:
        out.update(
            {
                "colors": sf.get("colors")
                or sorted({c for f in sf.get("card_faces") or [] for c in f.get("colors") or []}),
                "color_identity": sf.get("color_identity") or [],
                "cmc": sf.get("cmc"),
                "power": face_field(sf, "power"),
                "toughness": face_field(sf, "toughness"),
                "loyalty": face_field(sf, "loyalty"),
                "keywords": sf.get("keywords") or [],
                "layout": sf.get("layout"),
                "legal": {f: s for f, s in (sf.get("legalities") or {}).items() if s != "not_legal"},
                "edhrec_rank": sf.get("edhrec_rank"),
                "games": sf.get("games") or [],
                "flavor_text": sf.get("flavor_text") or None,
                "artist": sf.get("artist") or None,
                "released_at": sf.get("released_at") or None,
                "set_name": sf.get("set_name") or None,
                "art_tags": atags.get(sf.get("illustration_id") or "", []),
                "reserved": bool(sf.get("reserved")),
            }
        )
        p = prints.get(row["oracle_id"])
        if p:
            out.update(
                {
                    "artists": sorted(p["artists"]),
                    "printings": p["printings"] or None,
                    "first_printed": p["first"],
                    "last_printed": p["last"],
                    "price_usd": p["usd"],
                    "languages": sorted(p["langs"]),
                    "pt_text": p["pt"][1] if p["pt"] else None,
                }
            )
    return out


def content_hash(urna: Path) -> str:
    bin_ = os.environ.get("URNA_BIN", "urna")
    meta = json.loads(subprocess.run([bin_, "inspect", "--json", str(urna)], check=True, capture_output=True).stdout)
    return meta["content_hash"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def load_rows(parquet: Path) -> list[dict]:
    files = sorted(parquet.glob("cards-*.parquet"))
    if not files:
        raise SystemExit(f"error: no cards-*.parquet under {parquet}")
    rows = pa.concat_tables([pq.read_table(f, columns=PARQUET_COLUMNS) for f in files]).sort_by("ordinal").to_pylist()
    if [r["ordinal"] for r in rows] != list(range(len(rows))):
        raise SystemExit("error: ordinals are not 0..n-1")
    return rows


def enrich(parquet: Path, bulks: Path) -> list[dict]:
    rows = load_rows(parquet)
    index = oracle_index(bulks / "oracle_cards.jsonl")
    rulings = rulings_index(bulks / "rulings.jsonl")
    otags = tag_index(bulks / "oracle_tags.jsonl", "oracle_id")
    atags = tag_index(bulks / "art_tags.jsonl", "illustration_id")
    all_cards = bulks / "all_cards.jsonl"
    prints = printings_index(all_cards) if all_cards.is_file() else {}
    return [card_row(r, index.get(r["oracle_id"]), rulings, otags, atags, prints) for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parquet", type=Path, required=True, help="dir with cards-*.parquet")
    ap.add_argument("--bulks", type=Path, required=True, help="dir with the decompressed scryfall jsonl bulks")
    ap.add_argument("--urna", type=Path, required=True, help="the .urna the rows are bound to")
    ap.add_argument("--out", type=Path, required=True, help="rows file, zstd json")
    args = ap.parse_args()

    cards = enrich(args.parquet, args.bulks)
    doc = {"content_hash": content_hash(args.urna), "rows": cards}
    raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(zstandard.ZstdCompressor(level=19).compress(raw))
    used = [n for n in BULKS if (args.bulks / f"{n}.jsonl").is_file()]
    (args.out.parent / "bulks.json").write_text(
        json.dumps({n: sha256_file(args.bulks / f"{n}.jsonl") for n in used}, indent=1) + "\n"
    )
    counts = {k: sum(1 for c in cards if c.get(k)) for k in ("tags", "rulings", "art_tags", "pt_text", "price_usd")}
    print(f"{args.out}: {len(cards)} rows, {len(raw)} bytes json, {args.out.stat().st_size} bytes zstd")
    print(f"present: {counts}; bulks: {used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
