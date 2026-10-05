[![urna: offline-first vector database, rust and python](https://raw.githubusercontent.com/hoffresearch/urna/v0.5.4/assets/image/urna-hoff-research-db-iage-thumb-git.png)](https://docs.urna.dev/)

38,627 Magic card scans and their text in one searchable `.urna` file, and what it cost to get there.

The source is about 4 GB of JPEG from Scryfall. The [Urna](https://github.com/hoffresearch/urna) forge packs the images as codec media and embeds them with clip, the card text with potion. It writes one memory-mapped file with the vectors, an HNSW index, BM25 and a graph inside. This repo is the benchmark that picked the recipes: what compresses, what keeps search working, what does not.

One file. No loose media dir, no sidecar index.

- Dataset: [brennercruvinel/mtg-urna-benchmark](https://huggingface.co/datasets/brennercruvinel/mtg-urna-benchmark) on Hugging Face: the ten `.urna` files with their sidecars, the cards as Parquet, and the `queries` and `qrels` tables
- Engine: [Urna](https://github.com/hoffresearch/urna), the single-file vector database that builds and reads the `.urna` files
- Source: Scryfall bulk data as cached by the Spellbook app; the Parquet snapshot pinned in `sources/sources.toml` rebuilds it
- Sister benchmark, text: [brennercruvinel/fakenews-ptbr-urna-benchmark](https://github.com/brennercruvinel/fakenews-ptbr-urna-benchmark) ([dataset](https://huggingface.co/datasets/brennercruvinel/fakenews-ptbr-urna-benchmark))

## Pick a build

| Profile   | Media                                        | File    | When                                        |
|-----------|----------------------------------------------|---------|---------------------------------------------|
| archive   | JPEG XL repack, byte-reversible              | 3.6 GB  | The originals must come back bit for bit     |
| neardup   | AV1, clustered order, per-segment gop probe  | 1.4 GB  | Corpora with reprints of the same art        |
| stills    | AV1 all-intra, tune still                    | 1.4 GB  | Unique images, the default                   |
| retrieval | AV1 all-intra, crf 50                        | 533 MB  | Search only, never display                   |
| stills-5models | stills, plus siglip2, jina and wemm image spaces | 1.4 GB | Finding a card's image by its name           |

All five share one content_hash: the same text and the same text vectors, with four media encodings and, in stills-5models, four more image models. A `urna://` citation resolves in any of them. stills-5models is the file to search: siglip2 finds a card from its name at rank 1 three times in four, where clip, the only image model of the other four, finds it once in ten.

## Results

Lossless tops out at 1.12x. JPEG is already entropy coded: tar plus zstd gives 1.00x and the byte-reversible repack of JPEG XL gives the 12%. The path we invented (lossless video over a semantic ordering) lost by more than three to one.

Lossy has two levers that do not depend on each other. The encoder's still-image tune is worth ten SSIMULACRA2 points at the same crf. Inter prediction over reprints is worth 29% when the same art repeats and nothing on unique cards, so the forge probes each segment and records why it vetoed.

Search does not fall where the eye falls. Going from crf 35 to crf 50 cuts the file by more than half and clip text-to-image hit@1 does not move. The cosine drift gate would have vetoed that file; drift measures stability, not utility. That is why the retrieval profile exists, and why the gate is getting a hit@k floor.

The rest, with the numbers: [RESULTS.md](RESULTS.md), generated from one `results.json` per experiment.

## Build one

```sh
export MTG_DATA=/path/to/Spellbook/data    # mtg.sqlite plus images/normal/front/
```

```sh
export URNA_REPO=/path/to/urna             # a checkout of hoffresearch/urna at v0.5.4 or later
```

```sh
urna build --spec profiles/stills.toml     # lands in candidates/stills/
```

```sh
python3 benchmark/tools/promote.py promote candidates/stills v0.3 stills
```

The source data is Scryfall bulk data as cached by the Spellbook app. No image bytes live here; the corpora under `benchmark/corpora/` are id lists with the rule that produced each one. Without the Spellbook cache, `prepare_from_hub.py` rebuilds `MTG_DATA` from the Parquet snapshot pinned in `sources/sources.toml` and checks it against the releases.

```sh
uv sync                                    # pyproject.toml + uv.lock; --extra forge adds torch, open_clip, transformers
```

```sh
uv run python benchmark/tools/prepare_from_hub.py     # MTG_DATA must be empty or absent
```

## Check a release from the hub

```sh
hf download brennercruvinel/mtg-urna-benchmark --repo-type dataset --include "release/v0.3/stills-5models/*" \
  --revision 125b3f25b731d0b9a7133c53e5987f0dcc5b707e --local-dir .
```

```sh
(cd release/v0.3/stills-5models && shasum -a 256 -c SHA256SUMS)
```

```sh
uv run python benchmark/tools/promote.py check release/v0.3/stills-5models    # urna CLI on PATH, or URNA_BIN
```

`check` wants the `.urna` and every sidecar listed in `SHA256SUMS` with a matching digest, and a `CITATION_KEY` equal to what `urna inspect --json` reads from the file. The candidates under `candidates/` pass the same check under the forge's `mtgdataset.*` names. Run from the repo root, the download lands on the tracked sidecars, so `git status` also says whether the hub copy differs from the one tracked here.

## Query one

Two different searches. A text query against the card text runs offline on the potion space and needs only the `urna` CLI and its setup:

```sh
urna retrieve release/v0.3/stills-5models/mtgdataset.urna "a white creature that gains life when it enters" -k 3 --format jsonl
```

Finding a card's image from text goes through an image model's text tower into that model's image space. For siglip2 that is the evaluator, offline, against a model snapshot pinned to one hub revision:

```sh
hf download timm/ViT-B-16-SigLIP2 open_clip_model.safetensors open_clip_config.json tokenizer.json tokenizer_config.json special_tokens_map.json --revision eee10eff6dd8cabae2d7f379d4e8cfcd352030aa
```

```sh
HF_HUB_OFFLINE=1 URNA_REPO=/path/to/urna uv run --extra forge python benchmark/tools/bench_full_corpus.py \
  release/v0.3/stills-5models/mtgdataset.urna --preset siglip2 --queries 20 --seed 7 --out siglip2-q20.json
```

The Urna checkout needs v0.5.3 or later, the first release with the pinned-snapshot loader (hoffresearch/urna #271 and #273; v0.5.1 resolves `refs/main` and fails offline here): it reads the weights and the tokenizer from `snapshots/<revision>` of the HF cache, never from `refs/main` or the hub name, so the run works with the network off. The evaluator refuses a model whose `model_hash` is not the one in the file. jina and wemm run their repo's code and also need `URNA_ALLOW_REMOTE_CODE="jina-v5-omni-nano,wemm-2b"`; clip and siglip2 do not. `docs/environment.md` has every model, its source and its hash.

The queries and their single relevant card are on the hub as the `queries` and `qrels` configs, written by `export_queries.py` from the lists under `benchmark/corpora/`.

## Check everything from scratch

```sh
sh benchmark/tools/clean_install_proof.sh /path/to/empty/dir
```

The script clones this repo and Urna, builds the Urna CLI and its Python extension, and runs what CI runs. It downloads `stills-5models` from the hub at the current revision and checks its `SHA256SUMS` and `promote.py check`, rebuilds the `queries` and `qrels` tables and compares them with the published ones, and rebuilds `MTG_DATA` from the pinned snapshot. It builds the 512-card sample twice and expects the same file both times, with every chunk a chunk of the release. Last, it runs siglip2 with the network denied and expects the recorded hit@k. It stops at the first failure and writes `record.json`. The run of 2026-10-05 against Urna v0.5.4, 24 steps in 29 minutes, is `benchmark/tests/data/clean-install-2026-10-05.json`; the first run, of 2026-10-03 at urna `main` `7ef2b725`, is `clean-install-2026-10-03.json`. It needs about 15 GB of disk, and macOS for `sandbox-exec`.

## Cards and chunks

One chunk per card, 38,627 in every file: the card name, the Portuguese printed name where Scryfall has one, the mana cost, the type line, rarity, set code and oracle text, rendered by the template in `profiles/*.toml`. The card's image is the chunk's media span in the same file. A card's key is `img_id|oracle_id`, and `ordinal` is its place in the card order every release shares (the `keys_hash` in `sources/sources.toml`).

`file_hash` names a file: the sha256 of its bytes, listed in each release's `SHA256SUMS`. `content_hash` names the content: every full-corpus file shares `sha256:cb8fdf8f13fa50f93969de7603386f1c2b117a5e4946c60ac9894a3c5a1f062b`, because it covers the text and the default text vectors and not the media or the extra image spaces. A `urna://<content_hash>/<chunk_id>` citation therefore resolves in any of them.

A `chunk_id` is derived from the canonical text, the `source_uri` (`item://mtgdataset/<key>`), the span (`ordinal`, `ordinal + 1`) and the chunker version. The v0.3 files were written before the rename from nest, under the domain `nest:chunk_id:v1`. Urna now derives ids under `urna:chunk_id:v1`, so a rebuild of the same cards gets other chunk ids, and a citation from one does not resolve in the other. `clean_install_proof.sh` checks its rebuilt sample against the release with the old domain.

<details>
<summary>Layout</summary>

```
profiles/                the five recipes
benchmark/experiments/   NN-slug/{README.md, results.json, table.md, specs/}; README.md explains the missing 04, 07 and 12
benchmark/corpora/       id lists per sample and per query set, each with the keys_hash of the card order
benchmark/tools/         render_report, export_corpora, export_queries, promote, candidate_sidecars, bench_full_corpus, clean_install_proof.sh, ...
benchmark/tests/         unit tests; the integration test runs the evaluator on a downloaded release
release/v0.3/<profile>/  build lock, stripped manifest, SHA256SUMS, CITATION_KEY
release/v0.3/candidates.json  the hub candidates by file_hash, content_hash and sidecar digests
docs/                    methodology, hypotheses, references, roadmap, glossary, changelog
```

`.urna` files, media and caches are gitignored. CI runs ruff, the unit tests, `export_corpora.py --check` (the lists against the pinned card order), `promote.py check-tracked` (the tracked sidecars against their `SHA256SUMS`) and `render_report.py --check`.

</details>

<details>
<summary>Reading</summary>

- [docs/methodology.md](docs/methodology.md): the three measurements kept apart (fidelity, drift, hit@k), and what the literature calls this
- [docs/hypotheses.md](docs/hypotheses.md): thirteen bets and how each one ended
- [docs/references.md](docs/references.md): set redundancy and album coding, coding for machines, the codecs and the containers next door
- [docs/roadmap.md](docs/roadmap.md): what is still open, one GitHub issue each

</details>

## License

The material comes from two owners, and no single license covers all of it.

- Code, specs and results in this repository: MIT (`LICENSE`).
- The card images and the card text (names, mana costs, type lines, oracle text) belong to Wizards of the Coast and were obtained through [Scryfall](https://scryfall.com/docs/api). This repository tracks none of them, but the Hugging Face dataset holds them: the original JPEGs in `data/cards-*.parquet`, the same JPEGs recoverable bit for bit from the archive release, AV1 and AVIF re-encodings in the other `.urna` files, and the text in every chunk. Neither MIT nor CC BY 4.0 applies to them. They are used under the [Wizards of the Coast Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy) and Scryfall's guidelines for its data and images: free access, no paywall, non-commercial, no claim of endorsement.
- What this project wrote on the hub (the sidecars, the `queries` and `qrels` tables, the dataset card): CC BY 4.0, except the card names and text they quote. A `.urna` file mixes both: the container, the vectors and the indexes are this project's work, the text and media inside are Wizards'. The files are distributed as a whole under the terms of the previous item, not under CC BY 4.0.

mtg-urna-benchmark is unofficial Fan Content permitted under the Fan Content Policy. Not approved/endorsed by Wizards. Portions of the materials used are property of Wizards of the Coast. ©Wizards of the Coast LLC.
