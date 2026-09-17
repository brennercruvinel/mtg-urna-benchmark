# mtg-nest-benchmark

38,627 magic card scans and their text in one searchable `.nest` file, and what it cost to get there.

the source is about 4 GB of jpeg from scryfall. the [nest](https://github.com/hoffresearch/nest) forge packs the images as codec media and embeds them with clip, the card text with potion. it writes one memory-mapped file with the vectors, an hnsw index, bm25 and a graph inside. this repo is the benchmark that picked the recipes: what compresses, what keeps search working, what does not.

one file. no loose media dir, no sidecar index.

## profiles

| profile   | media                                        | file    | when                                        |
|-----------|----------------------------------------------|---------|---------------------------------------------|
| archive   | jpeg xl repack, byte-reversible              | 3.6 GB  | the originals must come back bit for bit     |
| neardup   | av1, clustered order, per-segment gop probe  | 1.4 GB  | corpora with reprints of the same art        |
| stills    | av1 all-intra, tune still                    | 1.4 GB  | unique images, the default                   |
| retrieval | av1 all-intra, crf 50                        | 533 MB  | search only, never display                   |

all four share one content_hash: same text, same vectors, four media encodings. a `nest://` citation resolves in any of them.

## what we found

lossless tops out at 1.12x. jpeg is already entropy coded: tar plus zstd gives 1.00x and the byte-reversible repack of jpeg xl gives the 12%. the path we invented (lossless video over a semantic ordering) lost by more than three to one.

lossy has two levers that do not depend on each other. the encoder's still-image tune is worth ten ssimulacra2 points at the same crf. inter prediction over reprints is worth 29% when the same art repeats and nothing on unique cards, so the forge probes each segment and records why it vetoed.

search does not fall where the eye falls. going from crf 35 to crf 50 cuts the file by more than half and clip text-to-image hit@1 does not move. the cosine drift gate would have vetoed that file; drift measures stability, not utility. that is why the retrieval profile exists, and why the gate is getting a hit@k floor.

the rest, with the numbers: [RESULTS.md](RESULTS.md), generated from one `results.json` per experiment.

## build one

```sh
export MTG_DATA=/path/to/Spellbook/data    # mtg.sqlite plus images/normal/front/
```

```sh
export NEST_REPO=/path/to/nest             # a checkout of hoffresearch/nest at v0.4.0 or later
```

```sh
nest build --spec profiles/stills.toml     # lands in candidates/stills/
```

```sh
python3 benchmark/tools/promote.py promote candidates/stills v0.3 stills
```

the source data is scryfall bulk data as cached by the spellbook app. no image bytes live here; the corpora under `benchmark/corpora/` are id lists with the rule that produced each one.

<details>
<summary>layout</summary>

```
profiles/                the four recipes
benchmark/experiments/   NN-slug/{README.md, results.json, table.md, specs/}
benchmark/corpora/       id lists per sample
benchmark/tools/         render_report, export_corpora, promote, measure_variants, ...
release/v0.3/<profile>/  build lock, stripped manifest, SHA256SUMS, CITATION_KEY
docs/                    methodology, hypotheses, references, roadmap, glossary, changelog
```

`.nest` files, media and caches are gitignored. `render_report.py --check` is the ci gate.

</details>

<details>
<summary>artifacts</summary>

the `.nest` files are on hugging face: [brennercruvinel/mtg-nest-benchmark](https://huggingface.co/datasets/brennercruvinel/mtg-nest-benchmark). `release/v0.3/<profile>/SHA256SUMS` pins the bytes, `CITATION_KEY` pins the identity read from inside the file with `nest inspect --json`.

</details>

<details>
<summary>reading</summary>

- [docs/methodology.md](docs/methodology.md): the three measurements kept apart (fidelity, drift, hit@k), and what the literature calls this
- [docs/hypotheses.md](docs/hypotheses.md): thirteen bets and how each one ended
- [docs/references.md](docs/references.md): set redundancy and album coding, coding for machines, the codecs and the containers next door
- [docs/roadmap.md](docs/roadmap.md): what is still open, one github issue each

</details>

## citing

`CITATION.cff`. the key of a specific file is its content_hash.

## license

code, specs and results: MIT (`LICENSE`). the `.nest` artifacts on hugging face: CC BY 4.0. the card images belong to wizards of the coast and are served by scryfall under their terms; this repo tracks none of them, and the compressed media inside each `.nest` is a derived encoding of that data, not a redistribution of the originals.
