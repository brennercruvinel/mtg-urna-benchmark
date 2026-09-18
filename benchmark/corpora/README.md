# corpora

six id lists, no image bytes. each file is `{"name", "n", "seed", "rule", "derived_from", "ids"}` and an id is the forge item key `img_id|oracle_id`, where img_id is the basename stem of the card's image_uri and oracle_id is the card. anyone with the spellbook sqlite (scryfall bulk data) can rebuild the exact sample from the rule; the `rule` field in each file is the authoritative statement, this readme only says what each list is for.

| list | n | seed | what it is | used by |
| --- | ---: | --- | --- | --- |
| sample-2048 | 2048 | none | `rows[int(i * 38627 / 2048)]` over the rows sorted by (img_id, oracle_id); the forge `--sample 2048`, evenly spaced, the `--seed` flag has no effect | experiments 01, 02, 08, 09 (corpus A), 10, 11 |
| sample-1500 | 1500 | none | the same rule with 1500; the five-model verification build | experiment 03 |
| frames-96 | 96 | 7 | `sorted(numpy.random.default_rng(7).choice(2048, 96, replace=False))` as ordinals of sample-2048; the quality sample of measure_variants.py and of the i-frame battery | experiments 02, 08, 11 |
| queries-100 | 100 | 7 | `sorted(numpy.random.default_rng(7).choice(38627, 100, replace=False))` over the full corpus in manifest order; urna_model_bench.py `--queries 100 --seed 7` | experiment 13 |
| reprints-2787 | 2787 | none | printings with a local normal/front file whose illustration_id occurs more than once among those files; 1359 groups; corpus B | experiment 09 |
| gate-48 | 48 | none | the forge's stratified_sample: items bucketed by (resolution, entropy, has_text), `members[::max(1, len // 12)][:12]` per sorted bucket, deterministic; read from the crf40 candidate manifest | experiment 13 (the crf auto ladder) |

the 2048 list was cross-checked against the control run manifest, 2048 of 2048 keys equal to the rule; the earlier "seed 42" was a provenance error. frames-96 and queries-100 also carry their `ordinals`, and gate-48 its bucket labels.

## regenerating

```
export MTG_DATA=/path/to/Spellbook/data     # mtg.sqlite plus images/normal/front
python3 benchmark/tools/export_corpora.py --dry-run   # shows which inputs would be used
python3 benchmark/tools/export_corpora.py
```

without `MTG_DATA` the tool falls back to a full-corpus manifest under `candidates/` or `release/` for the row order, and it skips reprints-2787 (needs the sqlite and the files on disk) and gate-48 (needs the crf40 candidate manifest). numpy is required for the two seeded draws. the tool refuses to write when the sqlite order and a manifest order disagree.
