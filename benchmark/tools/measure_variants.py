#!/usr/bin/env python3
"""uniform quality/size measurement over every variant in benchmark/runs/.

for each run: media bytes on disk, file count, urna bytes, encode time
from the manifest, crf chosen, and on the same deterministic 96-item
sample (numpy default_rng(7)) SSIMULACRA2 (letterboxed source vs decoded
frame) and clip cosine drift. lossless backends are asserted, not scored.

writes benchmark/experiments/02-av1-variants/measurements.json (the raw
record, byte-identical on replay) and derives from it the two rendered
results files: 01-baselines/results.json and 02-av1-variants/results.json.

a run whose media dir was pruned keeps its previous measurements.json
entry verbatim (that is how the 15 rows survive without 1 GB of media).

usage (from the repo root, with the urna venv python):
  export URNA_REPO=/path/to/urna MTG_DATA="/path/to/Spellbook/data"
  $URNA_REPO/.venv/bin/python benchmark/tools/measure_variants.py [--no-baselines]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_env as env  # noqa: E402

SAMPLE_N = 96
SEED = 7
MEASURED_DATE = "2026-08-31"  # date the media was last measured for real
EXP_VARIANTS = env.EXPERIMENTS / "02-av1-variants"
EXP_BASELINES = env.EXPERIMENTS / "01-baselines"
MEASUREMENTS = EXP_VARIANTS / "measurements.json"
# report order: ruler first, then lossless, then the av1 knob isolation, then image codecs and single-file builds
ORDER = [
    "control",
    "jxl-transcode",
    "jxl-lossless",
    "av1-v02-crf35-s8",
    "av1-still-s6-crf35",
    "av1-fps30-intra-crf35",
    "av1-inter-crf35",
    "av1-fps30-inter-crf35",
    "av1-cluster-crf35",
    "av1-auto-dualgate",
    "avif-crf35",
    "selfcontained-still-s6",
    "selfcontained-neardup",
    "selfcontained-jxl-transcode",
    "selfcontained-avif",
]


class MediaPruned(FileNotFoundError):
    """the whole media dir is gone: replay the previous entry verbatim."""


def _forge():
    """import the urna forge lazily: only real measurement needs torch and ffmpeg."""
    env.add_urna_to_path()
    import numpy as np
    from PIL import Image

    from forge import image_media, model_registry
    from forge.image_decode import decode_avif, decode_frame, decode_jxl
    from forge.quality_gate import _ssimulacra2

    return np, Image, image_media, model_registry, decode_avif, decode_frame, decode_jxl, _ssimulacra2


def measure_variant(run: Path, clip_holder: dict) -> dict | None:
    mf = run / "mtgdataset.manifest.json"
    if not mf.is_file():
        return None
    media_dir = run / "mtgdataset.media"
    if not media_dir.is_dir():
        raise MediaPruned(str(media_dir))
    np, Image, image_media, model_registry, decode_avif, decode_frame, decode_jxl, ssim2 = _forge()
    manifest = json.loads(mf.read_text())
    media = manifest["media"]
    backend = media["backend"]
    files = [p for p in media_dir.rglob("*") if p.is_file()]
    items = [it for it in manifest["items"] if it.get("media_uri")]
    rng = np.random.default_rng(SEED)
    idx = sorted(rng.choice(len(items), size=min(SAMPLE_N, len(items)), replace=False).tolist())
    sample = [items[i] for i in idx]
    canvas = tuple(media["canvas"]) if media.get("canvas") else None
    src_paths = [env.expand_path(it["image_path"]) for it in sample]

    def decoded(uri: str):
        rel_uri, frame = image_media.parse_media_uri(uri)
        path = media_dir / rel_uri
        if frame is not None:
            return decode_frame(path, canvas, frame, fps=int(media.get("fps", 1)))
        if backend == "avif":
            return decode_avif(path)
        if backend in ("jxl", "jxl-transcode"):
            return decode_jxl(path)
        return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)

    result = {
        "backend": backend,
        "media_bytes": sum(p.stat().st_size for p in files),
        "media_files": len(files),
        "urna_bytes": (run / "mtgdataset.urna").stat().st_size,
        "encode_s": manifest["timings"].get("media"),
        "embed_clip_s": manifest["timings"].get("embed.clip-vit-b32"),
        "n_items": manifest["n_items"],
        "source_bytes": media.get("source_bytes"),
        "crf_chosen": media.get("crf"),
        "quality_gate": media.get("quality_gate", {}).get("chosen")
        if isinstance(media.get("quality_gate"), dict)
        else None,
    }
    src_arrays, dec_arrays, scores = [], [], []
    with tempfile.TemporaryDirectory(prefix="urna-bench-q-") as tmp:
        tmp = Path(tmp)
        for i, (it, sp) in enumerate(zip(sample, src_paths, strict=True)):
            with Image.open(sp) as img:
                src = np.asarray(
                    image_media.letterbox(img, canvas) if canvas else img.convert("RGB"),
                    dtype=np.uint8,
                )
            dec = decoded(it["media_uri"])
            src_arrays.append(src)
            dec_arrays.append(dec)
            a, b = tmp / f"s{i:03d}.png", tmp / f"d{i:03d}.png"
            Image.fromarray(src).save(a)
            Image.fromarray(dec).save(b)
            scores.append(ssim2(a, b))
    sc = np.asarray(scores)
    result["ssimulacra2"] = {
        "p50": round(float(np.percentile(sc, 50)), 2),
        "p10": round(float(np.percentile(sc, 10)), 2),
        "min": round(float(sc.min()), 2),
    }
    result["pixel_lossless_sample"] = bool(
        all(np.array_equal(s, d) for s, d in zip(src_arrays, dec_arrays, strict=True))
    )
    # jxl honesty: PIL and djxl round the same jpeg differently, so the ssim
    # above is a decoder artifact, not codec loss. the build's own decisions
    # are the authority for the lossless claim.
    decisions = media.get("decisions") or []
    if backend == "jxl-transcode" and decisions:
        result["byte_lossless_verified"] = all(
            d.get("verified") for d in decisions if d["action"] == "transcode"
        ) and all(d["action"] in ("transcode", "copied") for d in decisions)
    elif backend == "jxl":
        result["pixel_lossless_own_decoder"] = True
    elif backend == "control":
        result["byte_lossless_verified"] = result["pixel_lossless_sample"]
    if "clip" not in clip_holder:
        clip_holder["clip"] = model_registry.create_embedder("clip-vit-b32", batch_size=32)
    clip = clip_holder["clip"]
    drift = np.sum(clip.embed_arrays(src_arrays) * clip.embed_arrays(dec_arrays), axis=1)
    result["clip_drift"] = {
        "p50": round(float(np.percentile(drift, 50)), 4),
        "p10": round(float(np.percentile(drift, 10)), 4),
        "min": round(float(drift.min()), 4),
    }
    result["sample_source_bytes"] = sum(p.stat().st_size for p in src_paths)
    return result


def baselines(control_manifest: Path) -> dict:
    """tar and tar+zstd-19 over the same source jpgs: the archive-tool ruler."""
    manifest = json.loads(control_manifest.read_text())
    paths = [env.expand_path(it["image_path"]) for it in manifest["items"] if it.get("image_path")]
    out = {"source_jpg_bytes": sum(p.stat().st_size for p in paths), "n_files": len(paths)}
    with tempfile.TemporaryDirectory(prefix="urna-bench-zip-") as tmp:
        tmp = Path(tmp)
        listing = tmp / "list.txt"
        listing.write_text("\n".join(str(p) for p in paths))
        tar_zst = tmp / "src.tar.zst"
        subprocess.run(
            ["tar", "--zstd", "-cf", str(tar_zst), "-T", str(listing)],
            check=True,
            env={**os.environ, "ZSTD_CLEVEL": "19"},
        )
        out["tar_zstd19_bytes"] = tar_zst.stat().st_size
        tar_plain = tmp / "src.tar"
        subprocess.run(["tar", "-cf", str(tar_plain), "-T", str(listing)], check=True)
        out["tar_bytes"] = tar_plain.stat().st_size
    return out


def lossless_class(r: dict) -> str:
    if r.get("byte_lossless_verified"):
        return "bytes"
    if r.get("pixel_lossless_own_decoder"):
        return "pixels"
    return "bytes" if r.get("pixel_lossless_sample") else "no"


def results_from_measurements(m: dict) -> tuple[dict, dict]:
    """derive the two rendered results.json documents from the raw record."""
    base = m["_baselines"]
    src = base["source_jpg_bytes"]
    baselines_doc = {
        "experiment": "01-baselines",
        "title": "archive-tool baselines over the 2048 source jpegs",
        "provenance": {
            "status": "measured",
            "source": "benchmark/experiments/02-av1-variants/measurements.json, key _baselines (measure_variants.py)",
            "date": MEASURED_DATE,
            "notes": "tar and tar --zstd (ZSTD_CLEVEL=19) over the same 2048 jpeg files the variants encode",
        },
        "constants": {"source_bytes": src},
        "tables": [
            {
                "title": "baselines",
                "columns": [
                    {"key": "baseline", "label": "baseline"},
                    {"key": "bytes", "label": "bytes", "fmt": "int"},
                    {"key": "mb", "label": "MB", "fmt": "mb", "from": "bytes"},
                    {"key": "ratio", "label": "ratio", "fmt": "ratio", "num": "source_bytes", "den": "bytes"},
                ],
                "rows": [
                    {"baseline": "source (jpeg)", "bytes": src},
                    {"baseline": "tar", "bytes": base["tar_bytes"]},
                    {"baseline": "tar + zstd-19", "bytes": base["tar_zstd19_bytes"]},
                ],
                "notes": [
                    f"{base['n_files']} files. generic archivers do not compress jpeg; every gain below comes from an image or video codec."
                ],
            }
        ],
    }
    rows = []
    names = [n for n in ORDER if n in m] + sorted(n for n in m if n not in ORDER and not n.startswith("_"))
    for name in names:
        r = m[name]
        s2, dr = r["ssimulacra2"], r["clip_drift"]
        rows.append(
            {
                "variant": name,
                "backend": r["backend"],
                "media_bytes": r["media_bytes"],
                "media_files": r["media_files"],
                "urna_bytes": r["urna_bytes"],
                "encode_s": r["encode_s"],
                "crf": r.get("crf_chosen"),
                "ssim2_p50": s2["p50"],
                "ssim2_p10": s2["p10"],
                "ssim2_min": s2["min"],
                "drift_p50": dr["p50"],
                "drift_p10": dr["p10"],
                "drift_min": dr["min"],
                "lossless": lossless_class(r),
                "manifest_source_bytes": r.get("source_bytes"),
            }
        )
    variants_doc = {
        "experiment": "02-av1-variants",
        "title": "codec variants on the 2048-card sample",
        "provenance": {
            "status": "measured",
            "source": "benchmark/experiments/02-av1-variants/measurements.json (measure_variants.py over benchmark/runs/<variant>)",
            "date": MEASURED_DATE,
            "notes": "media dirs were pruned after measurement; the .urna, manifest and build lock of every run remain under benchmark/runs/. "
            "quality on 96 frames (numpy default_rng(7).choice(2048, 96)): SSIMULACRA2 letterboxed source vs decoded frame, clip cosine drift source vs decoded. "
            "the 2048-card sample is evenly spaced (rows[int(i * 38627 / 2048)] over rows sorted by (img_id, oracle_id)); the seed flag has no effect. "
            "selfcontained-neardup here is the pre-fix probe build (inter chosen, quality degraded); the .urna now on disk is the post-fix rebuild (intra, 73127600 bytes). "
            "manifest_source_bytes for the avif rows is the letterboxed png intermediate (avif backend bug), the ratio column uses the jpeg source.",
        },
        "constants": {"source_bytes": src},
        "tables": [
            {
                "title": "variants",
                "columns": [
                    {"key": "variant", "label": "variant"},
                    {"key": "media_bytes", "label": "media bytes", "fmt": "int"},
                    {"key": "media_mb", "label": "media MB", "fmt": "mb", "from": "media_bytes"},
                    {"key": "ratio", "label": "ratio", "fmt": "ratio", "num": "source_bytes", "den": "media_bytes"},
                    {"key": "media_files", "label": "files", "fmt": "int"},
                    {"key": "urna_bytes", "label": "urna bytes", "fmt": "int"},
                    {"key": "encode_s", "label": "encode s", "fmt": "f1"},
                    {"key": "crf", "label": "crf"},
                    {"key": "ssim2_p50", "label": "ssim2 p50", "fmt": "f2"},
                    {"key": "ssim2_p10", "label": "p10", "fmt": "f2"},
                    {"key": "ssim2_min", "label": "min", "fmt": "f2"},
                    {"key": "drift_p10", "label": "clip drift p10", "fmt": "f4"},
                    {"key": "lossless", "label": "lossless"},
                ],
                "rows": rows,
                "notes": [
                    "lossless column: bytes = original jpeg bytes reconstructible (verified in build), pixels = decoded pixels preserved by the codec's own decoder, no = lossy.",
                    "the jxl rows score ssim2 92.8 because PIL and djxl round the same jpeg differently; the transcode is bit-exact (2048/2048 sha256 round-trips in the build).",
                ],
            }
        ],
    }
    return baselines_doc, variants_doc


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"written: {env.rel(path)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--no-baselines", action="store_true", help="keep the previous _baselines entry instead of re-running tar/zstd"
    )
    ap.add_argument("--dry-run", action="store_true", help="list the runs and what would happen, write nothing")
    args = ap.parse_args()
    previous = json.loads(MEASUREMENTS.read_text()) if MEASUREMENTS.is_file() else {}
    runs = sorted(p for p in env.RUNS.iterdir() if p.is_dir()) if env.RUNS.is_dir() else []
    if args.dry_run:
        for run in runs:
            state = "media present" if (run / "mtgdataset.media").is_dir() else "media pruned, replay"
            print(f"{run.name}: {state}")
        print(f"baselines: {'kept' if args.no_baselines else 'recomputed from source jpegs'}")
        return 0
    results: dict[str, dict] = {}
    clip_holder: dict = {}
    for run in runs:
        print(f"[measure] {run.name}...", flush=True)
        try:
            r = measure_variant(run, clip_holder)
        except FileNotFoundError as e:
            r = previous.get(run.name)
            if r is None:
                raise
            if not isinstance(e, MediaPruned):
                # a file vanished mid-measurement: keep the row, say so
                r["media_pruned"] = f"media deleted after measurement ({e.filename})"
            print(f"[measure] {run.name}: media pruned, keeping previous entry", flush=True)
        if r:
            results[run.name] = r
    if args.no_baselines and "_baselines" in previous:
        results["_baselines"] = previous["_baselines"]
    else:
        print("[measure] archive baselines...", flush=True)
        results["_baselines"] = baselines(env.RUNS / "control" / "mtgdataset.manifest.json")
    MEASUREMENTS.write_text(json.dumps(results, indent=1))
    print(f"written: {env.rel(MEASUREMENTS)}")
    base_doc, var_doc = results_from_measurements(results)
    write_json(EXP_BASELINES / "results.json", base_doc)
    write_json(EXP_VARIANTS / "results.json", var_doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
