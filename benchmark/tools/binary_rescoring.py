#!/usr/bin/env python3
"""binary hamming prefilter with int8 rescoring: how much recall a 1-bit index keeps.

the urna int8 ladder stores one byte per dimension and searches it with an
hnsw over the int8 rows. a 1-bit-per-dimension index is 8x smaller still and
searches with popcount. the question is whether a hamming top-K over the
sign bits, rescored with the int8 dot on those K rows, finds the same
neighbours as the exact f32 search, and at what K.

input: a forge embed-cache npz (float32 rows of one space). ground truth:
exact f32 cosine top-k per query row, the query itself excluded. queries are
corpus rows, so this measures the index, not a task.

usage (repo root):
  python3 benchmark/tools/binary_rescoring.py ~/.cache/urna/embed/siglip2/<hash>.npz \\
      --key image_unique --out data/binary.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np


def l2n(x: np.ndarray) -> np.ndarray:
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)


def to_int8(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """symmetric per-row int8: scale = max|x| / 127, like a per-vector absmax ladder."""
    scale = np.maximum(np.abs(x).max(axis=1, keepdims=True), 1e-12) / 127.0
    return np.clip(np.round(x / scale), -127, 127).astype(np.int8), scale.astype(np.float32)


def to_bits(x: np.ndarray) -> np.ndarray:
    return np.packbits(x > 0, axis=1)


def hamming_to_all(q_bits: np.ndarray, bits: np.ndarray, popcount: np.ndarray) -> np.ndarray:
    return popcount[np.bitwise_xor(bits, q_bits[None, :])].sum(axis=1)


def topk(scores: np.ndarray, k: int, exclude: int) -> np.ndarray:
    scores = scores.copy()
    scores[exclude] = -np.inf
    idx = np.argpartition(-scores, k)[:k]
    return idx[np.argsort(-scores[idx])]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("npz")
    ap.add_argument("--key", default="image_unique")
    ap.add_argument("--out", required=True)
    ap.add_argument("--queries", type=int, default=1000)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--candidates", default="20,50,100,200,400,800")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    x = l2n(np.load(args.npz)[args.key].astype(np.float32))
    n, dim = x.shape
    rng = np.random.default_rng(args.seed)
    queries = np.sort(rng.choice(n, args.queries, replace=False))
    q8, s8 = to_int8(x)
    bits = to_bits(x)
    popcount = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)
    cands = [int(c) for c in args.candidates.split(",")]

    truth = {}
    t_exact = 0.0
    for q in queries:
        t = time.perf_counter()
        truth[int(q)] = set(topk(x @ x[q], args.k, q).tolist())
        t_exact += time.perf_counter() - t

    # int8 exact: the dot on the quantized rows, rescaled per row
    hit_int8 = 0.0
    t_int8 = 0.0
    q8f = q8.astype(np.float32) * s8
    for q in queries:
        t = time.perf_counter()
        got = topk(q8f @ q8f[q], args.k, q)
        t_int8 += time.perf_counter() - t
        hit_int8 += len(set(got.tolist()) & truth[int(q)]) / args.k

    # binary top-K then int8 rescoring on those K
    per_k = {}
    for K in cands:
        hit = 0.0
        t_bin = 0.0
        for q in queries:
            t = time.perf_counter()
            h = hamming_to_all(bits[q], bits, popcount).astype(np.int32)
            h[q] = 1 << 30
            cand = np.argpartition(h, K)[:K]
            got = cand[np.argsort(-(q8f[cand] @ q8f[q]))[: args.k]]
            t_bin += time.perf_counter() - t
            hit += len(set(got.tolist()) & truth[int(q)]) / args.k
        per_k[K] = {"recall_at_k": round(hit / len(queries), 4), "ms_per_query": round(1000 * t_bin / len(queries), 2)}
        print(K, per_k[K], flush=True)

    # binary alone, no rescoring: the hamming top-k as the answer
    hit_bin = 0.0
    for q in queries:
        h = hamming_to_all(bits[q], bits, popcount).astype(np.int32)
        h[q] = 1 << 30
        got = np.argpartition(h, args.k)[: args.k]
        hit_bin += len(set(got.tolist()) & truth[int(q)]) / args.k

    payload = {
        "npz": Path(args.npz).name,
        "key": args.key,
        "n": n,
        "dim": dim,
        "queries": len(queries),
        "k": args.k,
        "bytes_per_row": {"f32": 4 * dim, "int8": dim, "binary": dim // 8},
        "exact_f32_ms_per_query": round(1000 * t_exact / len(queries), 2),
        "int8_exact": {
            "recall_at_k": round(hit_int8 / len(queries), 4),
            "ms_per_query": round(1000 * t_int8 / len(queries), 2),
        },
        "binary_alone": {"recall_at_k": round(hit_bin / len(queries), 4)},
        "binary_then_int8": per_k,
    }
    Path(args.out).write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps({k: v for k, v in payload.items() if k != "binary_then_int8"}))


if __name__ == "__main__":
    main()
