#!/usr/bin/env python3
"""random-access cost per media backend: ms to get one card's pixels out of a .urna.

the compression tables say how many bytes a profile saves; this says what a
reader pays to open one card. every backend the forge ships decodes through
a child process (ffmpeg for the av1 stream, avifdec for avif, djxl for jxl),
so the numbers here are end to end: blob lookup, process spawn, seek, decode.
that is the real cost today, not a kernel benchmark.

per file, on a fixed sample of item ordinals:
  av1 stream (one blob)     decode_frame_ms      one ffmpeg per card, -ss seek to the frame
                            batched10_per_frame  decode_frames_at with 10 hits in one ffmpeg,
                                                 divided by 10 (the batched path urna offers)
  per-image blobs           blob_bytes_ms        mmap lookup of the encoded bytes
                            blob_plus_decode_ms  bytes written to a temp file, then decoded

usage (repo root, URNA_REPO set):
  python3 benchmark/tools/measure_latency.py --out data/latency.json \\
      av1:stills=candidates/stills/mtgdataset.urna \\
      avif:avif-q48=candidates/v03-avif-q48/mtgdataset.urna \\
      jxl:archive=candidates/archive/mtgdataset.urna
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
import time
from pathlib import Path

import numpy as np

import _bench_env as env

env.add_urna_to_path()
import urna  # noqa: E402

from forge.image_decode import decode_avif, decode_frame, decode_frames_at, decode_jxl  # noqa: E402

CANVAS = (488, 680)
DECODERS = {"avif": (decode_avif, ".avif"), "jxl": (decode_jxl, ".jxl")}


def sample_ordinals(n_items: int, n: int, seed: int) -> list[int]:
    rng = np.random.default_rng(seed)
    return sorted(rng.choice(n_items, n, replace=False).tolist())


def timed(fn, ordinals: list[int]) -> dict:
    ms = []
    for i in ordinals:
        t = time.perf_counter()
        fn(i)
        ms.append((time.perf_counter() - t) * 1000)
    return {
        "p50": round(statistics.median(ms), 2),
        "p90": round(float(np.percentile(ms, 90)), 2),
        "p99": round(float(np.percentile(ms, 99)), 2),
        "mean": round(statistics.mean(ms), 2),
        "n": len(ms),
    }


def measure_stream(path: Path, ordinals: list[int]) -> dict:
    f = urna.open(str(path))
    refs = f.blob_refs()
    tmp = Path(tempfile.mkdtemp()) / "stream.mp4"
    t = time.perf_counter()
    tmp.write_bytes(f.blob_bytes(0))
    export_ms = (time.perf_counter() - t) * 1000
    out = {
        "kind": "stream",
        "file_bytes": path.stat().st_size,
        "blobs": len(refs),
        "export_once_ms": round(export_ms, 1),
        "decode_frame_ms": timed(lambda i: decode_frame(tmp, CANVAS, i), ordinals),
    }
    batches = [ordinals[k : k + 10] for k in range(0, len(ordinals) - 9, 10)]
    per_frame = []
    for batch in batches:
        t = time.perf_counter()
        frames = decode_frames_at(tmp, CANVAS, batch)
        per_frame.append((time.perf_counter() - t) * 1000 / len(frames))
    out["batched10_per_frame_ms"] = {
        "p50": round(statistics.median(per_frame), 2),
        "mean": round(statistics.mean(per_frame), 2),
        "batches": len(batches),
    }
    tmp.unlink()
    return out


def measure_per_image(path: Path, ordinals: list[int], kind: str) -> dict:
    decode, ext = DECODERS[kind]
    f = urna.open(str(path))
    refs = f.blob_refs()
    tmpd = Path(tempfile.mkdtemp())

    def full(i: int) -> None:
        p = tmpd / f"{i}{ext}"
        p.write_bytes(f.blob_bytes(i))
        decode(p)
        p.unlink()

    return {
        "kind": "per-image",
        "file_bytes": path.stat().st_size,
        "blobs": len(refs),
        "blob_bytes_ms": timed(lambda i: f.blob_bytes(i), ordinals),
        "blob_plus_decode_ms": timed(full, ordinals),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+", help="kind:name=path, kind in av1|avif|jxl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--items", type=int, default=38627, help="item count the ordinals are drawn over")
    args = ap.parse_args()

    ordinals = sample_ordinals(args.items, args.n, args.seed)
    results = {}
    for target in args.targets:
        kind, rest = target.split(":", 1)
        name, raw = rest.split("=", 1)
        path = Path(raw)
        if not path.is_file():
            env.die(f"{target}: {path} is not a file")
        t0 = time.perf_counter()
        r = measure_stream(path, ordinals) if kind == "av1" else measure_per_image(path, ordinals, kind)
        r["path"] = env.rel(path)
        r["wall_s"] = round(time.perf_counter() - t0, 1)
        results[name] = r
        print(name, json.dumps(r), flush=True)
    payload = {
        "sample": {"n": args.n, "seed": args.seed, "items": args.items, "ordinals": ordinals},
        "load": os.getloadavg(),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(payload, indent=1) + "\n")


if __name__ == "__main__":
    main()
