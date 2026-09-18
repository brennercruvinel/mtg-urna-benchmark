#!/usr/bin/env python3
"""generate one forge spec per sample-2048 variant.

every variant shares the same source, sample and two-model roster (potion
text default + clip image space, the drift gate model), so the only thing
that moves between runs is the [media] block. specs land in
benchmark/experiments/02-av1-variants/specs/<variant>.toml with the output
dir benchmark/runs/<variant> and ${MTG_DATA} sources.

the 2048 sample is not in the spec: it comes from the cli flag
  urna build --spec benchmark/experiments/02-av1-variants/specs/<variant>.toml --sample 2048
and is evenly spaced over the sorted rows (rows[int(i * n / 2048)]), so it
is identical across variants and independent of any seed.

usage (repo root): python3 benchmark/tools/gen_specs.py [--dry-run] [--out DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_env as env  # noqa: E402

SPECS = env.EXPERIMENTS / "02-av1-variants" / "specs"
DB = "${MTG_DATA}/mtg.sqlite"
IMG = "${MTG_DATA}/images/normal/front/{img_id[0]}/{img_id[1]}/{img_id}.jpg"

HEAD = f"""[corpus]
name = "mtgdataset"
title = "MTG dataset bench variant"
chunker_version = "mtgdataset/1"
reproducible = true

[source]
kind = "sqlite"
db = "{DB}"
query = \"\"\"
SELECT oracle_id, name, mana_cost, type_line, oracle_text, rarity, set_code, image_uri
FROM cards WHERE image_uri IS NOT NULL
\"\"\"
order_by = ["img_id", "oracle_id"]

[source.derive]
img_id = "basename_stem(image_uri)"

[source.text]
template = \"\"\"
{{name}}
{{mana_cost}}; {{type_line}}
[{{rarity}}, {{set_code}}]
{{oracle_text}}
\"\"\"

[source.image]
path_template = "{IMG}"
label_template = "{{name}}"
"""

MODELS = """
[[models]]
preset = "potion"
text = "default"

[[models]]
preset = "clip-vit-b32"
image = "space"

[build]
preset = "hybrid"
dtype = "int8"
with_graph = true
"""

QUALITY = """
[media.quality]
gate_model = "clip-vit-b32"
visual_floor_p10 = 85
visual_floor_min = 72
drift_floor_p10 = 0.98
crf_ladder = [30, 35, 40, 45]
sample_per_bucket = 12
buckets = ["resolution", "entropy", "has_text"]
"""

CLUSTER = """
[media.cluster]
space = "clip-vit-b32"
threshold = 0.92
"""

STILL_S6 = 'backend = "av1"\ncrf = 35\ntune = "still"\nspeed = 6\ngop = "intra"\norder = "none"'

# variant name -> [media] body lines
VARIANTS: dict[str, str] = {
    # v0.2 replica: what produced the 1.86 GB corpus of the previous generation
    "av1-v02-crf35-s8": 'backend = "av1"\ncrf = 35\ntune = "default"\nspeed = 8\ngop = "intra"\norder = "none"',
    # knob isolation: tune=still + speed 6, same crf
    "av1-still-s6-crf35": STILL_S6,
    # dual quality gate picks the crf
    "av1-auto-dualgate": 'backend = "av1"\ncrf = "auto"\ntune = "still"\nspeed = 6\ngop = "intra"\norder = "none"',
    # inter-frame prediction, source order
    "av1-inter-crf35": 'backend = "av1"\ncrf = 35\ntune = "still"\nspeed = 6\ngop = "inter"\norder = "none"',
    # semantic ordering + per-segment gop probe: the similar-dataset lever
    "av1-cluster-crf35": 'backend = "av1"\ncrf = 35\ntune = "still"\nspeed = 6\ngop = "auto"\norder = "cluster"',
    # the field report "accelerated the video, size halved": isolate the fps
    # knob alone (all-intra). if this matches still-s6 byte for byte the
    # gain came from somewhere else than playback speed.
    "av1-fps30-intra-crf35": 'backend = "av1"\ncrf = 35\ntune = "still"\nspeed = 6\nfps = 30\ngop = "intra"\norder = "none"',
    # fps 30 + inter together: the closest replica of the field experiment
    "av1-fps30-inter-crf35": 'backend = "av1"\ncrf = 35\ntune = "still"\nspeed = 6\nfps = 30\ngop = "inter"\norder = "none"',
    # image-codec baselines
    "avif-crf35": 'backend = "avif"\ncrf = 35',
    # true lossless pixels
    "jxl-lossless": 'backend = "jxl"',
    # bit-exact jpeg recompression (the only lossless claim on jpg sources)
    "jxl-transcode": 'backend = "jxl-transcode"',
    # letterboxed lossless control (ruler)
    "control": 'backend = "control"',
    # single-file .urna per backend type: media inlined via the 0x17 blob
    # section. neardup uses shard_size=512 so the 2048 sample actually
    # exercises the per-segment gop probe (4 shards).
    "selfcontained-still-s6": STILL_S6,
    "selfcontained-neardup": 'profile = "near-dup"\ncrf = 35\nspeed = 6\nshard_size = 512',
    "selfcontained-jxl-transcode": 'profile = "archive"',
    "selfcontained-avif": 'backend = "avif"\ncrf = 35',
}


def spec_for(name: str, media_body: str) -> str:
    parts = [HEAD]
    shard = "" if "shard_size" in media_body else "shard_size = 2048\n"
    parts.append(f"\n[media]\n{media_body}\n{shard}dedup = true\n")
    if 'crf = "auto"' in media_body:
        parts.append(QUALITY)
    if 'order = "cluster"' in media_body or 'profile = "near-dup"' in media_body:
        parts.append(CLUSTER)
    parts.append(MODELS)
    embed = "embed_media = true\n" if name.startswith("selfcontained-") else ""
    parts.append(f"""
[output]
mode = "single"
dir = "benchmark/runs/{name}"
provenance = "standard"
{embed}""")
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=SPECS, help="spec directory (default: the 02-av1-variants specs)")
    ap.add_argument("--dry-run", action="store_true", help="print the spec names and write nothing")
    args = ap.parse_args()
    if args.dry_run:
        for name in VARIANTS:
            print(f"would write {env.rel(args.out / (name + '.toml'))}")
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    for name, media in VARIANTS.items():
        (args.out / f"{name}.toml").write_text(spec_for(name, media))
        print(f"wrote {env.rel(args.out / (name + '.toml'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
