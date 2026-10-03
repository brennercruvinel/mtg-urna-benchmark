![urna: offline-first vector database, rust and python](https://raw.githubusercontent.com/hoffresearch/urna/main/assets/images/urna-hoff-research-db-thumb.png)

38,627 Magic card scans and their text in one searchable `.urna` file, and what it cost to get there.

The source is about 4 GB of JPEG from Scryfall. The [Urna](https://github.com/hoffresearch/urna) forge packs the images as codec media and embeds them with clip, the card text with potion. It writes one memory-mapped file with the vectors, an HNSW index, BM25 and a graph inside. This repo is the benchmark that picked the recipes: what compresses, what keeps search working, what does not.

One file. No loose media dir, no sidecar index.

## Profiles

| Profile   | Media                                        | File    | When                                        |
|-----------|----------------------------------------------|---------|---------------------------------------------|
| archive   | JPEG XL repack, byte-reversible              | 3.6 GB  | The originals must come back bit for bit     |
| neardup   | AV1, clustered order, per-segment gop probe  | 1.4 GB  | Corpora with reprints of the same art        |
| stills    | AV1 all-intra, tune still                    | 1.4 GB  | Unique images, the default                   |
| retrieval | AV1 all-intra, crf 50                        | 533 MB  | Search only, never display                   |

All four share one content_hash: same text, same vectors, four media encodings. A `urna://` citation resolves in any of them.

## What we found

Lossless tops out at 1.12x. JPEG is already entropy coded: tar plus zstd gives 1.00x and the byte-reversible repack of JPEG XL gives the 12%. The path we invented (lossless video over a semantic ordering) lost by more than three to one.

Lossy has two levers that do not depend on each other. The encoder's still-image tune is worth ten SSIMULACRA2 points at the same crf. Inter prediction over reprints is worth 29% when the same art repeats and nothing on unique cards, so the forge probes each segment and records why it vetoed.

Search does not fall where the eye falls. Going from crf 35 to crf 50 cuts the file by more than half and clip text-to-image hit@1 does not move. The cosine drift gate would have vetoed that file; drift measures stability, not utility. That is why the retrieval profile exists, and why the gate is getting a hit@k floor.

The rest, with the numbers: [RESULTS.md](RESULTS.md), generated from one `results.json` per experiment.

## Build one

```sh
export MTG_DATA=/path/to/Spellbook/data    # mtg.sqlite plus images/normal/front/
```

```sh
export URNA_REPO=/path/to/urna             # a checkout of hoffresearch/urna at v0.5.0 or later
```

```sh
urna build --spec profiles/stills.toml     # lands in candidates/stills/
```

```sh
python3 benchmark/tools/promote.py promote candidates/stills v0.3 stills
```

The source data is Scryfall bulk data as cached by the Spellbook app. No image bytes live here; the corpora under `benchmark/corpora/` are id lists with the rule that produced each one.

<details>
<summary>Layout</summary>

```
profiles/                the four recipes
benchmark/experiments/   NN-slug/{README.md, results.json, table.md, specs/}; README.md explains the missing 04, 07 and 12
benchmark/corpora/       id lists per sample
benchmark/tools/         render_report, export_corpora, promote, measure_variants, ...
release/v0.3/<profile>/  build lock, stripped manifest, SHA256SUMS, CITATION_KEY
docs/                    methodology, hypotheses, references, roadmap, glossary, changelog
```

`.urna` files, media and caches are gitignored. `render_report.py --check` is the CI gate.

</details>

<details>
<summary>Artifacts</summary>

The `.urna` files are on Hugging Face: [brennercruvinel/mtg-urna-benchmark](https://huggingface.co/datasets/brennercruvinel/mtg-urna-benchmark). `release/v0.3/<profile>/SHA256SUMS` pins the bytes, `CITATION_KEY` pins the identity read from inside the file with `urna inspect --json`.

</details>

<details>
<summary>Reading</summary>

- [docs/methodology.md](docs/methodology.md): the three measurements kept apart (fidelity, drift, hit@k), and what the literature calls this
- [docs/hypotheses.md](docs/hypotheses.md): thirteen bets and how each one ended
- [docs/references.md](docs/references.md): set redundancy and album coding, coding for machines, the codecs and the containers next door
- [docs/roadmap.md](docs/roadmap.md): what is still open, one GitHub issue each

</details>

## Citing

`CITATION.cff`. The key of a specific file is its content_hash.

## License

Code, specs and results: MIT (`LICENSE`). The `.urna` artifacts on Hugging Face: CC BY 4.0. The card images belong to Wizards of the Coast and are served by Scryfall under their terms; this repo tracks none of them, and the compressed media inside each `.urna` is a derived encoding of that data, not a redistribution of the originals.
