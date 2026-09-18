#!/usr/bin/env python3
"""quality knob for a target ssimulacra2: the calibration step of experiment 11, kept this time.

a fixed crf compares bytes at a knob, not at a quality. this bisects each
backend's knob until the mean ssimulacra2 on the 96-frame quality sample
(frames-96, the ordinals of sample-2048 that measure_variants.py uses)
brackets the target, then encodes the full 2048-card sample at the two
bracketing knobs for the bytes. the report carries both brackets and the
bytes interpolated at the target, so two backends are compared at the same
fidelity instead of the same number.

backends and knobs (the forge's own encoders, letterbox to 488x680):
  av1-still-s6     ffmpeg + libsvtav1, all-intra, tune still, preset 6, crf 20..63 (higher = smaller)
  av1-default-s6   the same with svt-av1's default tune
  avif-s6, avif-s8 avifenc -q 20..90 (higher = better), speed 6 or 8, yuv420

usage (repo root, MTG_DATA and URNA_REPO set):
  python3 benchmark/tools/crf_for_target.py --target 61.96 --out data/target.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

import _bench_env as env

env.add_urna_to_path()
from forge.image_decode import decode_avif, decode_frames  # noqa: E402
from forge.image_encode import encode_av1  # noqa: E402
from forge.image_encode_still import encode_avif  # noqa: E402
from forge.image_media import letterbox  # noqa: E402
from forge.quality_gate import _ssimulacra2  # noqa: E402

CANVAS = (488, 680)
BACKENDS = {
    "av1-still-s6": {"kind": "av1", "tune": "still", "lo": 20, "hi": 63, "higher_is_smaller": True},
    "av1-default-s6": {"kind": "av1", "tune": "default", "lo": 20, "hi": 63, "higher_is_smaller": True},
    "avif-s6": {"kind": "avif", "speed": 6, "lo": 20, "hi": 90, "higher_is_smaller": False},
    "avif-s8": {"kind": "avif", "speed": 8, "lo": 20, "hi": 90, "higher_is_smaller": False},
}


def corpus_paths() -> tuple[list[Path], list[int]]:
    root = env.require_data_root()
    ids = json.load(open(env.CORPORA / "sample-2048.json"))["ids"]
    ordinals = json.load(open(env.CORPORA / "frames-96.json"))["ordinals"]
    paths = []
    for key in ids:
        img = key.split("|", 1)[0]
        paths.append(root / "images" / "normal" / "front" / img[0] / img[1] / f"{img}.jpg")
    return paths, ordinals


def letterboxed(paths: list[Path], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    pngs = []
    for i, p in enumerate(paths):
        dst = out / f"{i:06d}.png"
        if not dst.exists():
            with Image.open(p) as img:
                letterbox(img, CANVAS).save(dst)
        pngs.append(dst)
    return pngs


def encode(
    backend: dict, pngs: list[Path], knob: int, work: Path, *, decode: bool = True
) -> tuple[int, list[np.ndarray]]:
    """bytes and, for the quality sample, the decoded frames in order."""
    if backend["kind"] == "av1":
        out = work / "stream.mp4"
        encode_av1(pngs, out, canvas=CANVAS, crf=knob, preset=6, keyint=1, tune=backend["tune"])
        frames = [f for batch in decode_frames(out, CANVAS) for f in batch] if decode else []
        size = out.stat().st_size
        out.unlink()
        return size, frames
    d = work / "avif"
    shutil.rmtree(d, ignore_errors=True)
    rec = encode_avif(pngs, d, quality=knob, yuv="420", speed=backend["speed"])
    frames = [decode_avif(p) for p in sorted(d.glob("*.avif"))] if decode else []
    shutil.rmtree(d)
    return rec["output_bytes"], frames


def mean_ssim2(src: list[Path], frames: list[np.ndarray], work: Path) -> float:
    scores = []
    for i, (s, f) in enumerate(zip(src, frames, strict=True)):
        d = work / f"d{i:03d}.png"
        Image.fromarray(f).save(d)
        scores.append(_ssimulacra2(s, d))
        d.unlink()
    return float(np.mean(scores))


def bisect(backend: dict, sample: list[Path], target: float, work: Path) -> list[dict]:
    """probe knobs until two adjacent ones bracket the target; every probe is kept."""
    lo, hi = backend["lo"], backend["hi"]
    probes: dict[int, float] = {}

    def q(knob: int) -> float:
        if knob not in probes:
            t = time.perf_counter()
            _, frames = encode(backend, sample, knob, work)
            probes[knob] = mean_ssim2(sample, frames, work)
            print(f"  {knob}: ssim2 {probes[knob]:.2f} ({time.perf_counter() - t:.0f}s)", flush=True)
        return probes[knob]

    # quality is monotone in the knob; a is the high-quality end, b the low one
    a, b = (lo, hi) if backend["higher_is_smaller"] else (hi, lo)
    if q(a) < target or q(b) > target:
        return [{"knob": k, "ssim2": round(v, 2)} for k, v in sorted(probes.items())]
    while abs(a - b) > 1:
        mid = (a + b) // 2
        if q(mid) >= target:
            a = mid
        else:
            b = mid
    return [{"knob": k, "ssim2": round(v, 2)} for k, v in sorted(probes.items())]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=float, default=61.96)
    ap.add_argument("--backends", default=",".join(BACKENDS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    paths, ordinals = corpus_paths()
    work = Path(tempfile.mkdtemp(prefix="target-"))
    pngs = letterboxed(paths, work / "png")
    sample = [pngs[i] for i in ordinals]
    source_bytes = sum(p.stat().st_size for p in paths)
    results = {}
    for name in args.backends.split(","):
        backend = BACKENDS[name]
        print(name, flush=True)
        probes = bisect(backend, sample, args.target, work)
        above = [p for p in probes if p["ssim2"] >= args.target]
        below = [p for p in probes if p["ssim2"] < args.target]
        key = (lambda p: p["knob"]) if backend["higher_is_smaller"] else (lambda p: -p["knob"])
        bracket = []
        if above:
            bracket.append(max(above, key=key))  # the smallest file still at or above the target
        if below:
            bracket.append(min(below, key=key))  # the first knob under it
        for p in bracket:
            t = time.perf_counter()
            size, _ = encode(backend, pngs, p["knob"], work, decode=False)
            p["bytes_2048"] = size
            p["encode_s_2048"] = round(time.perf_counter() - t, 1)
            print(f"  2048 cards at {p['knob']}: {size} bytes", flush=True)
        interp = None
        if len(bracket) == 2 and bracket[0]["ssim2"] != bracket[1]["ssim2"]:
            hi, lo = bracket
            w = (args.target - lo["ssim2"]) / (hi["ssim2"] - lo["ssim2"])
            interp = int(round(lo["bytes_2048"] + w * (hi["bytes_2048"] - lo["bytes_2048"])))
        results[name] = {"probes": probes, "bracket": bracket, "bytes_at_target_interpolated": interp}
    shutil.rmtree(work, ignore_errors=True)
    payload = {
        "target_ssim2_mean": args.target,
        "quality_sample": "frames-96 (96 ordinals of sample-2048, default_rng(7))",
        "bytes_sample": "sample-2048",
        "source_bytes_2048": source_bytes,
        "results": results,
    }
    Path(args.out).write_text(json.dumps(payload, indent=1) + "\n")


if __name__ == "__main__":
    main()
