# scalars

the card columns the `.urna` carries inside itself (chunk_scalars, section 0x0D) and the schema an app reads to filter, facet and draw them. urna issue hoffresearch/urna#208 added the section and the schema; hoffresearch/urna#626 is this dataset's side.

- `schema.json`: one entry per column: name, kind (int, real, bool, text, uuid, enum, enum_list, enum_map, chunk), the label an app shows, the roles (filter, facet, label, rank, tag, display), the search prefix (`t:creature c:r pow>=3 otag:"spot removal" usd<1`) and how a value is drawn
- `dataset.json`: where the columns came from, with the sha256 of `bulks.json`
- `bulks.json`: the sha256 of each decompressed scryfall bulk of 2026-10-16 the rows were built from; `benchmark/tools/fetch_bulks.sh` downloads and checks them
- `media.json`: how the stored images derive from the originals (avif, q48, lossy)

## build the columns into a file

```sh
benchmark/tools/fetch_bulks.sh                                  # five bulks, 2.9 GB decompressed
```

```sh
hf download brennercruvinel/mtg-urna-benchmark --repo-type dataset --include "data/*" --local-dir hub
```

```sh
uv run python benchmark/tools/enrich.py --parquet hub/data \
  --bulks "${XDG_CACHE_HOME:-$HOME/.cache}/urna/scryfall" \
  --urna candidates/v03-avif-q48/mtgdataset.urna --out candidates/v03-avif-q48-scalars/rows.json.zst
```

```sh
urna scalars candidates/v03-avif-q48/mtgdataset.urna --rows candidates/v03-avif-q48-scalars/rows.json.zst \
  --schema scalars/schema.json --dataset scalars/dataset.json --media scalars/media.json \
  --out candidates/v03-avif-q48-scalars/mtgdataset.urna
```

the output keeps the content_hash of the input (`sha256:cb8fdf8f...`), so every `urna://` citation of the v0.3 files resolves in it; only the file_hash changes. 56 columns over 38,627 chunks, 32.5 MB of columns on top of the 1.20 GB file.

## what is in the columns

| source | columns |
| --- | --- |
| the parquet snapshot | name, pt_name, mana_cost, type_line, rarity, set_code, kind |
| scryfall oracle-cards | colors, color_identity, cmc, power, toughness, loyalty, keywords, layout, legal (one column per format), edhrec_rank, games, flavor_text, artist, released_at, set_name, reserved |
| scryfall rulings | rulings, the official rulings joined by newline |
| scryfall oracle-tags, art-tags | tags (functional, from tagger.scryfall.com), art_tags (what the illustration shows) |
| scryfall all-cards | artists, printings, first_printed, last_printed, price_usd (lowest), languages, pt_text (the latest portuguese printing) |

decks, combos and play statistics are not here: no source publishes them under terms that allow redistribution.
