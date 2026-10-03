#!/usr/bin/env python3
"""The text-to-image queries of the utility experiments and their correspondences, as parquet.

The benchmark's own evaluation, unchanged: a query is the template
"artwork of the card {label}" over one card's label, it is searched in a
model's image space, and it has exactly one relevant item, that card's own
row (its key, its ordinal, its chunk in every v0.3 file). hit@k is whether
that row is in the top k. There is no graded relevance.

  queries   query_id, list, experiment, gallery, ordinal, key, label, text, art_series
  qrels     query_id, key, ordinal, relevance (always 1)

The lists are the tracked ones under benchmark/corpora (export_corpora.py
derives and checks them); `all` is every card, the queries of experiment 20.
`gallery` says what the query was searched against: the full corpus, or the
512-card sample of experiment 15. art_series marks the "name // name" rows
experiment 20 reports apart. The card order and labels come from a release
items.jsonl.gz whose keys_hash must be the pinned one.

usage (repo root):
  python3 benchmark/tools/export_queries.py --out queries [--items release/v0.3/stills/items.jsonl.gz]
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_env as env  # noqa: E402
import export_corpora as ec  # noqa: E402

TEMPLATE = "artwork of the card {label}"
# list -> (experiment, gallery); `all` is the card order itself
LISTS = {
    "queries-100": ("13-retrieval-crf", "full"),
    "queries-1000": ("14-utility-ladder", "full"),
    "queries-200": ("15-models-over-crf", "sample-512"),
    "all": ("20-full-corpus-utility", "full"),
}


def art_series(label: str) -> bool:
    faces = label.split(" // ")
    return len(faces) == 2 and faces[0] == faces[1]


def tables(items: list[dict], corpora: Path) -> tuple[list[dict], list[dict]]:
    """queries and qrels rows, in list order then query order."""
    by_key = {it["key"]: it for it in items}
    queries, qrels = [], []
    for name, (experiment, gallery) in LISTS.items():
        if name == "all":
            keys = [it["key"] for it in items]
        else:
            keys = json.loads((corpora / f"{name}.json").read_text())["ids"]
        width = len(str(len(keys) - 1))
        for i, key in enumerate(keys):
            it = by_key.get(key)
            if it is None:
                env.die(f"{name}: {key} is not in the card order")
            qid = f"{name}/{i:0{width}d}"
            queries.append(
                {
                    "query_id": qid,
                    "list": name,
                    "experiment": experiment,
                    "gallery": gallery,
                    "ordinal": it["ordinal"],
                    "key": key,
                    "label": it["label"],
                    "text": TEMPLATE.format(label=it["label"]),
                    "art_series": art_series(it["label"]),
                }
            )
            qrels.append({"query_id": qid, "key": key, "ordinal": it["ordinal"], "relevance": 1})
    return queries, qrels


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--items", type=Path, help="a release items.jsonl.gz (default: local release, else the pinned hub revision)"
    )
    ap.add_argument("--corpora", type=Path, default=env.CORPORA)
    args = ap.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        env.die(f"{env.rel(args.out)} is not empty")
    path, where = ec.items_path(args.items)
    with gzip.open(path, "rt") as f:
        items = sorted((json.loads(line) for line in f if line.strip()), key=lambda it: it["ordinal"])
    if ec.keys_hash([it["key"] for it in items]) != ec.snapshot_pin()["keys_hash"]:
        env.die(f"{where} is not the pinned card order")
    queries, qrels = tables(items, args.corpora)

    import pyarrow as pa
    import pyarrow.parquet as pq

    args.out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("queries", queries), ("qrels", qrels)):
        path = args.out / f"{name}.parquet"
        pq.write_table(pa.Table.from_pylist(rows), path)
        print(f"{env.rel(path)}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
