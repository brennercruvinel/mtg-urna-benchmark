#!/usr/bin/env python3
"""golden frame per cluster: does the order inside a reprint group change the inter bytes?

inter prediction only helps when a frame can be predicted from the ones
before it. on the reprints corpus (every printing on disk whose
illustration_id occurs more than once) three orderings of the same 2787
frames go through the same inter encode (keyint 16, scd off, crf 35,
preset 6, the neardup recipe without the probe):

  sorted    the corpus order by id, groups scattered over the stream
  grouped   groups contiguous, members in id order
  golden    groups contiguous, the most central member first (smallest mean
            phash hamming to the rest of its group), then the others

usage (repo root, MTG_DATA and URNA_REPO set):
  python3 benchmark/tools/golden_frame.py --out data/golden.json
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

import numpy as np
from phash_prefilter import hamming_matrix, load_corpus, phash64

import _bench_env as env

env.add_urna_to_path()
from forge.image_encode import encode_av1  # noqa: E402

CANVAS = (488, 680)
INTER = {"crf": 35, "preset": 6, "keyint": 16, "tune": "default"}


def orderings(ids: list[str], ill: dict[str, str], hashes: np.ndarray) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for i, key in enumerate(ids):
        groups.setdefault(ill[key], []).append(i)
    ordered_groups = sorted(groups.values(), key=lambda g: ids[g[0]])
    grouped = [i for g in ordered_groups for i in g]
    dist = hamming_matrix(hashes)
    golden = []
    for g in ordered_groups:
        sub = dist[np.ix_(g, g)].astype(np.float64)
        centre = g[int(np.argmin(sub.mean(axis=1)))]
        golden.append(centre)
        golden.extend(i for i in g if i != centre)
    return {"sorted": list(range(len(ids))), "grouped": grouped, "golden": golden}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ids, paths, ill = load_corpus()
    hashes = np.array([phash64(p) for p in paths], dtype=np.uint64)
    orders = orderings(ids, ill, hashes)
    work = Path(tempfile.mkdtemp(prefix="golden-"))
    source_bytes = sum(p.stat().st_size for p in paths)
    results = {}
    for name, order in orders.items():
        out = work / f"{name}.mp4"
        t = time.perf_counter()
        rec = encode_av1([paths[i] for i in order], out, canvas=CANVAS, **INTER)
        results[name] = {
            "bytes": out.stat().st_size,
            "ratio_vs_source": round(source_bytes / out.stat().st_size, 3),
            "encode_s": round(time.perf_counter() - t, 1),
            "keyint": rec.get("toolchain", {}).get("params", {}).get("keyint"),
        }
        out.unlink()
        print(name, results[name], flush=True)
    base = results["sorted"]["bytes"]
    for r in results.values():
        r["pct_vs_sorted"] = round(100 * (r["bytes"] / base - 1), 2)
    payload = {
        "corpus": "reprints-2787",
        "n": len(ids),
        "groups": len(set(ill[k] for k in ids)),
        "source_bytes": source_bytes,
        "recipe": INTER,
        "results": results,
    }
    Path(args.out).write_text(json.dumps(payload, indent=1) + "\n")


if __name__ == "__main__":
    main()
