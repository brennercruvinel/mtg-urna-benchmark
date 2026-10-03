#!/usr/bin/env python3
"""text-to-image hit@k with the whole corpus as queries, one image space at a time.

urna_model_bench.py draws a few hundred query items and re-embeds their
source images for its stability tiers, which is what makes it expensive.
this tool asks only the utility question and asks it of every item: embed
one text query per card with the model's text tower, search the space the
.urna already stores, and count the hits by chunk_id. 38627 queries give a
standard error of about 0.0015 on hit@1 instead of the 0.02 to 0.03 of a
200-query run, and a bootstrap interval comes with the point.

Reads the manifest of a candidate (<name>.manifest.json) or of a release
(manifest.json + items.jsonl.gz), and refuses a model whose model_hash or dim
does not match the file before it embeds a single query.

usage (repo root, URNA_REPO set, URNA_ALLOW_REMOTE_CODE for jina and wemm):
  python3 benchmark/tools/bench_full_corpus.py release/v0.3/stills-5models/mtgdataset.urna \\
      --preset siglip2 --template "artwork of the card {label}" --out data/full.siglip2.json
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

import _bench_env as env
from _release import check_items, check_model_identity, load_build_manifest

env.add_urna_to_path()
import urna  # noqa: E402

from forge import model_registry  # noqa: E402


def bootstrap_ci(hits: np.ndarray, n: int = 1000, seed: int = 7) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = np.array([hits[rng.integers(0, len(hits), len(hits))].mean() for _ in range(n)])
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("index", type=Path)
    ap.add_argument("--preset", required=True)
    ap.add_argument("--template", default="artwork of the card {label}")
    ap.add_argument("--queries", type=int, default=0, help="0 = every item")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("-k", type=int, nargs="+", default=[1, 5, 10])
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    manifest = load_build_manifest(args.index)
    items = manifest["items"]
    labels = [it.get("label") for it in items]
    if not all(labels):
        env.die("manifest items carry no label; rebuild with output.provenance = standard")
    spaces = [s for s in manifest["spaces"] if s["modality"] == "image" and s["preset"] == args.preset]
    if not spaces:
        env.die(f"no image space for preset {args.preset} in {args.index}")
    if "text" not in model_registry.get_preset(args.preset).modalities:
        env.die(f"{args.preset} has no text tower")

    idx = list(range(len(items)))
    if args.queries:
        rng = np.random.default_rng(args.seed)
        idx = sorted(rng.choice(len(items), min(args.queries, len(items)), replace=False).tolist())

    allowed = frozenset(p.strip() for p in os.environ.get("URNA_ALLOW_REMOTE_CODE", "").split(",") if p.strip())
    recipe = manifest["models"][args.preset].get("recipe", {})
    adapter = model_registry.create_embedder(
        args.preset, allow_remote_code=allowed, allow_heavy=True, usage=recipe, batch_size=args.batch
    )
    db = urna.open(str(args.index))
    info = db.inspect()
    check_items(items, info["n_chunks"], db.chunk_ids())
    check_model_identity(args.preset, adapter.model_hash, adapter.dim, manifest, info.get("spaces") or [], spaces)
    texts = [args.template.format(label=labels[i]) for i in idx]
    t0 = time.perf_counter()
    chunks = []
    for start in range(0, len(texts), 1024):
        chunks.append(adapter.embed_texts(texts[start : start + 1024], role="query"))
    tq_full = np.concatenate(chunks)
    embed_s = time.perf_counter() - t0

    chunk_ids = db.chunk_ids()
    ks = sorted(args.k)
    report = {
        "index": env.rel(args.index),
        "file_hash": info.get("file_hash"),
        "content_hash": info.get("content_hash"),
        "model_hash": adapter.model_hash,
        "preset": args.preset,
        "template": args.template,
        "queries": len(idx),
        "text_embed_s": round(embed_s, 1),
        "text_queries_per_s": round(len(idx) / max(embed_s, 1e-9), 1),
        "spaces": {},
    }
    for space in spaces:
        name, dim = space["name"], space["dim"]
        tq = model_registry.slice_renorm(tq_full, dim) if dim else tq_full
        hits = {k: np.zeros(len(idx), dtype=np.uint8) for k in ks}
        ranks = np.full(len(idx), -1, dtype=np.int32)
        t0 = time.perf_counter()
        for j, i in enumerate(idx):
            expected = chunk_ids[items[i]["ordinal"]]
            ranked = [h.chunk_id for h in db.search_space(name, tq[j].tolist(), max(ks))]
            for k in ks:
                hits[k][j] = expected in ranked[:k]
            if expected in ranked:
                ranks[j] = ranked.index(expected)
        search_s = time.perf_counter() - t0
        rep = {"dim": dim, "search_s": round(search_s, 1), "hit": {}, "band_bytes": space.get("band_bytes")}
        for k in ks:
            h = hits[k]
            p = float(h.mean())
            lo, hi = bootstrap_ci(h)
            rep["hit"][f"@{k}"] = {
                "value": round(p, 4),
                "se": round(float(np.sqrt(p * (1 - p) / len(h))), 4),
                "ci95": [round(lo, 4), round(hi, 4)],
            }
        found = ranks[ranks >= 0]
        rep["mrr_at_max_k"] = round(float((1.0 / (found + 1)).sum() / len(idx)), 4)
        report["spaces"][name] = rep
        print(name, json.dumps(rep["hit"]), flush=True)
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
