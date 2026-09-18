#!/usr/bin/env python3
"""the corpus as parquet: one row per card, the scan as an image column, the same order as the .urna.

the .urna is the artifact and nothing on the hub can render it. this writes
the same 38,627 rows as sharded parquet with the jpeg bytes in an `image`
column the hub viewer knows how to draw, plus the fields the text template
was rendered from and the ordinal that maps the row to its chunk in every
release. it is a view of the corpus, not a replacement for the file: no
vectors, no index.

row order is the forge's total order by (img_id, oracle_id), read back from
the release's items.jsonl.gz so the ordinal here is the ordinal there.

usage (repo root, MTG_DATA set):
  python3 benchmark/tools/export_parquet.py release/v0.3/stills-5models --out data --shards 8
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

from datasets import Dataset, Features, Image, Value

import _bench_env as env

FEATURES = Features(
    {
        "ordinal": Value("int32"),
        "key": Value("string"),
        "oracle_id": Value("string"),
        "img_id": Value("string"),
        "name": Value("string"),
        "pt_name": Value("string"),
        "mana_cost": Value("string"),
        "type_line": Value("string"),
        "rarity": Value("string"),
        "set_code": Value("string"),
        "oracle_text": Value("string"),
        "art_series": Value("bool"),
        "image_sha256": Value("string"),
        "image_bytes": Value("int32"),
        "image": Image(),
    }
)


def rows(release: Path, root: Path):
    con = sqlite3.connect(root / "mtg.sqlite")
    cards = {
        r[0]: r
        for r in con.execute(
            "select oracle_id, name, mana_cost, type_line, rarity, set_code, oracle_text "
            "from cards where image_uri is not null"
        )
    }
    pt = dict(con.execute("select oracle_id, printed_name from names_localized where lang = 'pt' and lang_rank = 1"))
    with gzip.open(release / "items.jsonl.gz", "rt") as f:
        for line in f:
            it = json.loads(line)
            img_id, oracle_id = it["key"].split("|", 1)
            c = cards[oracle_id]
            path = root / "images" / "normal" / "front" / img_id[0] / img_id[1] / f"{img_id}.jpg"
            data = path.read_bytes()
            label = it["label"]
            faces = label.split(" // ")
            yield {
                "ordinal": it["ordinal"],
                "key": it["key"],
                "oracle_id": oracle_id,
                "img_id": img_id,
                "name": c[1],
                "pt_name": pt.get(oracle_id) or "",
                "mana_cost": c[2] or "",
                "type_line": c[3] or "",
                "rarity": c[4] or "",
                "set_code": c[5] or "",
                "oracle_text": c[6] or "",
                "art_series": len(faces) == 2 and faces[0] == faces[1],
                "image_sha256": hashlib.sha256(data).hexdigest(),
                "image_bytes": len(data),
                "image": {"bytes": data, "path": f"{img_id}.jpg"},
            }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("release", type=Path, help="a release dir with items.jsonl.gz")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--shards", type=int, default=8)
    args = ap.parse_args()

    root = env.require_data_root()
    ds = Dataset.from_generator(rows, gen_kwargs={"release": args.release, "root": root}, features=FEATURES)
    args.out.mkdir(parents=True, exist_ok=True)
    total = 0
    for i in range(args.shards):
        shard = ds.shard(num_shards=args.shards, index=i, contiguous=True)
        p = args.out / f"cards-{i:05d}-of-{args.shards:05d}.parquet"
        shard.to_parquet(p)
        total += p.stat().st_size
        print(p.name, len(shard), "rows", p.stat().st_size, "bytes", flush=True)
    print("rows", len(ds), "parquet bytes", total)


if __name__ == "__main__":
    main()
