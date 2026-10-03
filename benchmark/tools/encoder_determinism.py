#!/usr/bin/env python3
"""does the encoder write the same bytes when the thread count changes?

the forge records the toolchain in every manifest because another encoder
version produces other bytes. this asks a narrower question on ONE
toolchain: same input, same parameters, different worker counts and a
repeat run. byte-identical output means the file_hash of a release is a
property of the recipe and the toolchain, not of the machine's core count.

three backends, the forge's own parameters:
  av1   ffmpeg + libsvtav1, all-intra, tune still, crf 35, preset 6, lp = 1 2 8 16 and 2 twice
  avif  avifenc -q 48 --speed 6 --yuv 420, -j 1 8 all and all twice
  jxl   cjxl --lossless_jpeg=1, --num_threads 1 8 and default twice

usage (repo root, MTG_DATA and URNA_REPO set):
  python3 benchmark/tools/encoder_determinism.py --n 256 --out data/determinism.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import _bench_env as env

env.add_urna_to_path()
from forge.image_encode import encode_av1  # noqa: E402
from forge.image_media import letterbox  # noqa: E402

CANVAS = (488, 680)
AV1 = {"crf": 35, "preset": 6, "keyint": 1, "tune": "still"}
AVIF = ["-q", "48", "--speed", "6", "--yuv", "420"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sample_paths(n: int) -> list[Path]:
    root = env.require_data_root()
    ids = json.load(open(env.CORPORA / "sample-2048.json"))["ids"]
    step = max(1, len(ids) // n)
    out = []
    for key in ids[::step][:n]:
        img = key.split("|", 1)[0]
        out.append(root / "images" / "normal" / "front" / img[0] / img[1] / f"{img}.jpg")
    return out


def run_av1(paths: list[Path], work: Path) -> dict:
    runs = {}
    for label, lp in (("lp1", 1), ("lp2_a", 2), ("lp2_b", 2), ("lp8", 8), ("lp16", 16)):
        out = work / f"{label}.mp4"
        t = time.perf_counter()
        encode_av1(paths, out, canvas=CANVAS, lp=lp, **AV1)
        runs[label] = {
            "lp": lp,
            "bytes": out.stat().st_size,
            "sha256": sha(out),
            "s": round(time.perf_counter() - t, 1),
        }
    return runs


def run_avif(paths: list[Path], work: Path) -> dict:
    from PIL import Image

    png_dir = work / "png"
    png_dir.mkdir()
    pngs = []
    for i, path in enumerate(paths):
        out = png_dir / f"{i:06d}.png"
        with Image.open(path) as img:
            letterbox(img, CANVAS).save(out)
        pngs.append(out)
    runs = {}
    for label, jobs in (("j1", "1"), ("j8", "8"), ("jall_a", "all"), ("jall_b", "all")):
        d = work / f"avif-{label}"
        d.mkdir()
        t = time.perf_counter()
        digest = hashlib.sha256()
        total = 0
        for png in pngs:
            out = d / (png.stem + ".avif")
            subprocess.run(["avifenc", "-j", jobs, *AVIF, str(png), str(out)], check=True, capture_output=True)
            digest.update(out.read_bytes())
            total += out.stat().st_size
        runs[label] = {
            "jobs": jobs,
            "bytes": total,
            "sha256": digest.hexdigest(),
            "s": round(time.perf_counter() - t, 1),
        }
        shutil.rmtree(d)
    return runs


def run_jxl(paths: list[Path], work: Path) -> dict:
    runs = {}
    for label, threads in (
        ("t1", ["--num_threads=1"]),
        ("t8", ["--num_threads=8"]),
        ("default_a", []),
        ("default_b", []),
    ):
        d = work / f"jxl-{label}"
        d.mkdir()
        t = time.perf_counter()
        digest = hashlib.sha256()
        total = 0
        for jpg in paths:
            out = d / (jpg.stem + ".jxl")
            subprocess.run(["cjxl", str(jpg), str(out), "--lossless_jpeg=1", *threads], check=True, capture_output=True)
            digest.update(out.read_bytes())
            total += out.stat().st_size
        runs[label] = {
            "threads": " ".join(threads) or "default",
            "bytes": total,
            "sha256": digest.hexdigest(),
            "s": round(time.perf_counter() - t, 1),
        }
        shutil.rmtree(d)
    return runs


def tool_version(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (p.stdout or p.stderr).strip().splitlines()[0][:120]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--out", required=True)
    ap.add_argument("--backends", default="av1,avif,jxl")
    args = ap.parse_args()

    paths = sample_paths(args.n)
    work = Path(tempfile.mkdtemp(prefix="determinism-"))
    results = {}
    for backend in args.backends.split(","):
        runs = {"av1": run_av1, "avif": run_avif, "jxl": run_jxl}[backend](paths, work)
        hashes = {r["sha256"] for r in runs.values()}
        results[backend] = {"runs": runs, "distinct_outputs": len(hashes), "deterministic": len(hashes) == 1}
        print(backend, "distinct outputs:", len(hashes), flush=True)
    shutil.rmtree(work, ignore_errors=True)
    payload = {
        "n": len(paths),
        "sample": "sample-2048 ids, every len/n-th, first n",
        "toolchain": {
            "ffmpeg": tool_version(["ffmpeg", "-version"]),
            "avifenc": tool_version(["avifenc", "--version"]),
            "cjxl": tool_version(["cjxl", "--version"]),
            "platform": tool_version(["uname", "-sm"]),
        },
        "results": results,
    }
    Path(args.out).write_text(json.dumps(payload, indent=1) + "\n")


if __name__ == "__main__":
    main()
