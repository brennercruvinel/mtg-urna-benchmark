#!/usr/bin/env python3
"""assemble results.json for 15-models-over-crf from the bench outputs and the
build manifests. stdlib only. run from the repo root:

  python3 benchmark/experiments/15-models-over-crf/assemble.py

reads  benchmark/runs/15-<variant>/mtgdataset.manifest.json  (media bytes, build-side embed rate and seconds per model)
       benchmark/experiments/15-models-over-crf/bench/<variant>.<preset>.json  (urna_model_bench output, one preset per file)
writes benchmark/experiments/15-models-over-crf/results.json

a missing bench file (a model that failed to load) leaves its cells as null,
which render_report.py prints as '-'.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUNS = REPO / "benchmark" / "runs"
N_QUERIES = 200

VARIANTS = [("lossless", "lossless (jxl-transcode)"), ("crf35", "av1 crf35"), ("crf50", "av1 crf50")]
MODELS = [
    ("clip-vit-b32", "clip-vit-b32", "clip ViT-B/32 (512d)"),
    ("siglip2", "siglip2", "siglip2 ViT-B/16 (768d)"),
    ("jina-v5-omni-nano", "jina-v5-omni-nano@256", "jina-v5-omni-nano @256"),
    ("wemm-2b", "wemm-2b@256", "wemm-2b @256"),
]


def load(p: Path):
    return json.loads(p.read_text()) if p.is_file() else None


def main() -> int:
    manifests = {v: load(RUNS / f"15-{v}" / "mtgdataset.manifest.json") for v, _ in VARIANTS}
    rows, deltas = [], []
    for preset, space, label in MODELS:
        per_variant = {}
        for v, vlabel in VARIANTS:
            m = manifests[v]
            b = load(HERE / "bench" / f"{v}.{preset}.json")
            sp = (b or {}).get("models", {}).get(preset, {}).get("spaces", {}).get(space)
            mm = (m or {}).get("models", {}).get(preset, {})
            row = {
                "model": label,
                "media": vlabel,
                "media_bytes": (m or {}).get("media", {}).get("output_bytes"),
                "identity_at_1": sp["t1_identity_recall"]["@1"] if sp else None,
                "drift_p10": sp["t2_drift_cosine"]["p10"] if sp else None,
                "drift_p50": sp["t2_drift_cosine"]["p50"] if sp else None,
                "txt_at_1": sp["t3_text_to_image_hit"]["@1"] if sp else None,
                "txt_at_5": sp["t3_text_to_image_hit"]["@5"] if sp else None,
                "txt_at_10": sp["t3_text_to_image_hit"]["@10"] if sp else None,
                "embed_items_per_s": mm.get("items_per_s"),
                # a 0.0 embed timing is a cache hit (the vectors came from the shared embed
                # cache, no model ran in that build), so the rate is unknown, not zero
                "embed_s": (m or {}).get("timings", {}).get(f"embed.{preset}") or None,
            }
            rows.append(row)
            per_variant[v] = row
        ref = per_variant["lossless"]

        def d(v: str, key: str):
            a, b = per_variant[v].get(key), ref.get(key)
            return None if a is None or b is None else round(a - b, 4)

        def z(v: str, key: str, n: int = N_QUERIES):
            # pooled binomial se of the difference of two hit rates at n queries each
            a, b = per_variant[v].get(key), ref.get(key)
            if a is None or b is None:
                return None
            se = math.sqrt(a * (1 - a) / n + b * (1 - b) / n)
            return None if se == 0 else round((a - b) / se, 2)

        deltas.append(
            {
                "model": label,
                "txt1_lossless": ref.get("txt_at_1"),
                "txt1_crf35": per_variant["crf35"].get("txt_at_1"),
                "d_txt1_crf35": d("crf35", "txt_at_1"),
                "txt1_crf50": per_variant["crf50"].get("txt_at_1"),
                "d_txt1_crf50": d("crf50", "txt_at_1"),
                "z_txt1_crf50": z("crf50", "txt_at_1"),
                "d_txt5_crf50": d("crf50", "txt_at_5"),
                "d_txt10_crf50": d("crf50", "txt_at_10"),
                "d_drift_crf50": d("crf50", "drift_p10"),
            }
        )

    n_items = next((m["n_items"] for m in manifests.values() if m), None)
    source_bytes = next((m["media"].get("source_bytes") for m in manifests.values() if m), None)
    doc = {
        "experiment": "15-models-over-crf",
        "title": "four image models over three media levels: who loses retrieval utility at crf50",
        "provenance": {
            "status": "measured",
            "source": "benchmark/runs/15-{lossless,crf35,crf50}/mtgdataset.manifest.json (media.output_bytes, models.<preset>.items_per_s, timings.embed.<preset>) and benchmark/experiments/15-models-over-crf/bench/<variant>.<preset>.json (urna_model_bench.py, 200 queries, default_rng(7), ruler 'artwork of the card {label}', hits matched by chunk_id)",
            "date": "2026-09-12",
            "notes": (
                f"one evenly spaced --sample 512 of the mtgdataset corpus ({n_items} items, chunker mtgdataset/1), "
                "the same cards in the three builds; potion text default plus four image spaces per build; "
                "embedding.image_input = decoded_media, so drift is source-embed vs the stored vector of the decoded frame; "
                "jina and wemm sliced to their validated mrl dim 256; mps fp16 for every torch model. "
                "the 200 query items are drawn by default_rng(7) over the 512, so identical across models and media levels. "
                "with n=200 one hit is 0.005 of txt@k; a delta needs to clear roughly 0.03 to 0.04 to be more than noise at this size."
            ),
        },
        "constants": {"source_bytes": source_bytes},
        "tables": [
            {
                "title": "model x media level (512-card sample, 200 queries)",
                "columns": [
                    {"key": "model", "label": "model"},
                    {"key": "media", "label": "media level"},
                    {"key": "media_bytes", "label": "media bytes", "fmt": "int"},
                    {"key": "ratio_media", "label": "ratio_media", "fmt": "ratio", "num": "source_bytes", "den": "media_bytes"},
                    {"key": "identity_at_1", "label": "identity@1", "fmt": "f3"},
                    {"key": "drift_p10", "label": "drift p10", "fmt": "f4"},
                    {"key": "drift_p50", "label": "drift p50", "fmt": "f4"},
                    {"key": "txt_at_1", "label": "txt@1", "fmt": "f3"},
                    {"key": "txt_at_5", "label": "txt@5", "fmt": "f3"},
                    {"key": "txt_at_10", "label": "txt@10", "fmt": "f3"},
                    {"key": "embed_items_per_s", "label": "embed it/s", "fmt": "f2"},
                    {"key": "embed_s", "label": "embed s", "fmt": "f1"},
                ],
                "rows": rows,
                "notes": [
                    "media bytes is the inlined media blob of each build (jxl-transcode for lossless, one all-intra av1 segment for crf35 and crf50); every row of a media level shares it. ratio_media divides the jpeg source bytes of the 512 sampled cards (constants.source_bytes, from the manifest) by it.",
                    "embed it/s and embed s are build side: items per second over the 512 decoded frames as the manifest recorded them (timings.embed.<preset>), so they include model load and the first-batch warmup on mps. a '-' is a cache hit: the lossless build ran twice (the first attempt died at wemm-2b before its weights had finished downloading) and the retry took clip, siglip2 and jina from the shared embed cache, so only wemm-2b has a measured rate on that row.",
                    "identity@1 (T1) is inflated by construction and only says the pipeline keeps its own signal; txt@k (T3) is the label ruler, a weak ground truth; T1, T2 and T3 are never aggregated.",
                ],
            },
            {
                "title": "txt@1 loss against the lossless reference, per model",
                "columns": [
                    {"key": "model", "label": "model"},
                    {"key": "txt1_lossless", "label": "txt@1 lossless", "fmt": "f3"},
                    {"key": "txt1_crf35", "label": "txt@1 crf35", "fmt": "f3"},
                    {"key": "d_txt1_crf35", "label": "delta crf35", "fmt": "f3"},
                    {"key": "txt1_crf50", "label": "txt@1 crf50", "fmt": "f3"},
                    {"key": "d_txt1_crf50", "label": "delta crf50", "fmt": "f3"},
                    {"key": "z_txt1_crf50", "label": "z crf50", "fmt": "f2"},
                    {"key": "d_txt5_crf50", "label": "delta txt@5 crf50", "fmt": "f3"},
                    {"key": "d_txt10_crf50", "label": "delta txt@10 crf50", "fmt": "f3"},
                    {"key": "d_drift_crf50", "label": "delta drift p10 crf50", "fmt": "f4"},
                ],
                "rows": deltas,
                "notes": [
                    "delta = lossy minus lossless on the same 200 queries; negative is a loss. 0.005 per query, so a delta inside about 0.03 is noise at n=200.",
                    "z = delta / sqrt(p_lossy(1-p_lossy)/200 + p_lossless(1-p_lossless)/200), the pooled binomial se of the difference; |z| below 2 is inside noise.",
                ],
            },
        ],
    }
    out = HERE / "results.json"
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"written: {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
