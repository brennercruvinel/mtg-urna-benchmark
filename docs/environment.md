# Environment

What each tool needs, and the exact toolchain the v0.3 files were built with. The build locks under `release/v0.3/*/build.lock.json` are the source of every version below.

## Python

`pyproject.toml` and `uv.lock` pin the environment; Python 3.12, as in every build lock.

```sh
uv sync                       # the tools that need no urna checkout
uv sync --extra forge         # plus the forge's packages, pinned to the v0.3 builds
```

## Tools without a checkout of Urna

`prepare_from_hub`, `export_parquet`, `export_corpora`, `render_report`, `sanitize_sidecars`, `binary_rescoring`, `phash_prefilter`, `lossless_battery` and `gen_specs` run on the base environment. `promote` also needs the `urna` CLI on the path (or `URNA_BIN`), installed from any channel in the [Urna README](https://github.com/hoffresearch/urna).

## Tools that need a checkout of Urna

`bench_full_corpus`, `candidate_sidecars`, `crf_for_target`, `encoder_determinism`, `golden_frame`, `measure_latency`, `measure_variants`, and `urna build --spec profiles/*.toml` import the forge from a checkout. The forge is not in the installed payload.

```sh
git clone https://github.com/hoffresearch/urna && git -C urna checkout v0.5.4
export URNA_REPO=$PWD/urna
cd urna && cargo build --release -p urna-bridge --features pyo3/extension-module \
  && cp target/release/lib_urna.dylib python/_urna.so && cd -      # lib_urna.so on linux
uv sync --extra forge
```

v0.5.0 is the first tag with the spec features the profiles use; v0.5.3 is the first with the pinned-snapshot loader a siglip2 query needs offline (hoffresearch/urna #271 and #273); v0.5.4 is the one these instructions name. It renames the crates (the extension is built as `urna-bridge`, `urna-python` before) and changes no format, runtime or API. The recorded siglip2 run was made at urna `main` `7ef2b725`, whose forge, query embedders, runtime and format code are identical to v0.5.3's and v0.5.4's. The v0.3 files were built with the forge of that period, before the rename (`built_with` in each `CITATION_KEY`).

## Models

The build locks record each model's `model_hash`, the fingerprint Urna checks at query time. They do not record the hub revision of each snapshot. A snapshot is the right one when its fingerprint equals the `model_hash` below; Urna refuses a query on a mismatch.

| Preset | Source | model_hash (release/v0.3 locks) |
|---|---|---|
| potion | `minishlab/potion-base-8M`, bundled with Urna | `sha256:8f2eb91a754b...` |
| clip-vit-b32 | open_clip `ViT-B-32`, pretrained `openai` | `sha256:76269ff6bb18...` |
| siglip2 | `timm/ViT-B-16-SigLIP2` at revision `eee10eff`, loaded as open_clip `ViT-B-16-SigLIP2` / `webli` | `sha256:a9946db1d336...` |
| jina-v5-omni-nano | `jinaai/jina-embeddings-v5-omni-nano`, remote code | `sha256:59a01c7cfdaf...` |
| wemm-2b | `tencent/WeMM-Embedding-2B`, remote code | `sha256:6b428bc1759f...` |

The full hashes are in `release/v0.3/stills-5models/build.lock.json`.

siglip2 is the one preset Urna pins to a hub revision: it loads the weights and the tokenizer from `snapshots/eee10eff6dd8cabae2d7f379d4e8cfcd352030aa` of the HF cache, never through `refs/main` or the hub name, so the five files `hf download timm/ViT-B-16-SigLIP2 open_clip_model.safetensors open_clip_config.json tokenizer.json tokenizer_config.json special_tokens_map.json --revision eee10eff6dd8cabae2d7f379d4e8cfcd352030aa` fetches are all a query needs, offline. Its tokenizer imports `transformers` (in the `forge` extra). A missing file is an error naming it and that command. `benchmark/tests/data/eval-siglip2-stills-5models-q20.json` records a 20-query run against urna `main` at `7ef2b725` with the network blocked and only that snapshot in the cache, before and after. clip still loads by tag through open_clip, which resolves `refs/main`: fetch it once without `--revision` before going offline. jina and wemm run remote code: the spec lists them in `output.allow_remote_code`, Urna checks every code file against its pinned SHA-256, and a query needs `URNA_ALLOW_REMOTE_CODE="jina-v5-omni-nano,wemm-2b"`.

## Codecs

| Binary | Version | Where it is recorded |
|---|---|---|
| ffmpeg, ffprobe | 9.0.1, with svt-av1 | every build lock, with the binary's SHA-256 |
| avifenc | libavif 1.4.2 with aom 3.15.0 | experiment 18 provenance |
| cjxl, djxl | 0.12.0 | binary SHA-256 in every build lock; version from experiment 18 (the locks could not read it) |
| ssimulacra2 | Homebrew build | binary SHA-256 in every build lock |

All on Apple M4, macOS 26. A build with other encoder versions produces other bytes (experiment 19 measured 1.5% for one aom step); the content_hash, which covers the text and the default text vectors, does not depend on them.

## Source data

`MTG_DATA` is the data root the profiles read. `benchmark/tools/prepare_from_hub.py` rebuilds it from the dataset's Parquet snapshot at the revision pinned in `sources/sources.toml`, and checks it against the releases (see that file).
