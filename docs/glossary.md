# glossary

the vocabulary of the benchmark and of the urna forge as it is used in `RESULTS.md`, the experiment readmes and the specs.

## profiles

stills: unique images. av1 all-intra, `tune=still`, single segment. `profiles/stills.toml`.

near-dup: corpora with near duplicates. `order=cluster` by clip cosine, `gop=auto` with a per-segment probe, `tune=still`. `profiles/neardup.toml`, the recommended default: on unique cards the probe vetoes inter on every segment and records why, on reprints it takes the 29%.

archive: bit-exact reversibility. jxl-transcode of the source jpeg, round-trip verified by sha256 at build and at validate. `profiles/archive.toml`.

retrieval-only: serves search, never display. visual floors dropped, av1 at a high fixed crf. `profiles/retrieval.toml` at crf50.

## the three classes of lossless

byte-reversible: the original jpeg bytes come back. jxl-transcode.

pixel-exact: a re-save with the same decoded pixels and different bytes. jpegtran, jpegoptim.

pixel-domain: the decoded pixels are recompressed by another codec; always larger than the jpeg it came from. webp lossless, ffv1, x264 qp0.

## the three measurement tiers

t1 identity: the source image of an item finds the item at rank 1. pipeline stability.

t2 drift: cosine between the embedding of the source and of the decoded frame, p10 over the sample. codec cost as the model sees it.

t3 hit@k: a text query finds the item within k. utility. the three are never aggregated.

## reproduction levels

l1: semantic reproduction, the same content.

l2: vector reproduction within a tolerance.

l3: byte-for-byte reproduction, the same file_hash. the build lock is what makes l3 claimable, and a mislabelled dtype in the model hash is enough for the lock to flag "l3 not claimable" on its own.

## corpus vocabulary

twins: two builds with the same content_hash and different media, for instance the sidecar and the embedded variant, or the av1 and avif candidates. citations are stable across twins by construction.

chrome: the frame, the text box and the other pixels every card shares regardless of its art. part of the inter gain on corpus B comes from chrome, not from repeated art.

corpus A: the 2048 unique cards of the sample (`benchmark/corpora/sample-2048.json`).

corpus B: 2787 printings of the same artwork in 1359 illustration_id groups (`benchmark/corpora/reprints-2787.json`).

## keys and mechanisms

triad: model_hash, corpus_input_hash and embedding_recipe_hash. the embed cache is keyed on the three and is invalid when any one changes.

identity n3: chunk_id and content_hash are the identity of an item and of a file. media uris stay outside the canonical sections, so re-encoding the media or swapping the backend does not change the content_hash; renaming the chunker does.

probe: a small encode of a window of the segment on both arms before deciding. the gop probe compares intra against inter on bytes and on ssimulacra2 (tolerance 2.0 points, contiguous windows when the order is engineered) and records `decision`, `overridden` and the reason per segment. the tune probe checks that the still-picture tune is accepted (it needs keyint=1) and records `tune_resolved`, 3 for the real tune or 4 for the ms-ssim fallback.

dual gate: `crf=auto`. a ladder of crf values, a stratified sample per bucket (resolution, entropy, has_text), and three floors: `visual_floor_p10`, `visual_floor_min` on ssimulacra2 and `drift_floor_p10` on clip cosine. the largest crf that passes every floor wins; when none passes the gate falls back to the smallest crf and writes a warning into the manifest.

`[media]` keys: `backend` (av1, avif, jxl, jxl-transcode, control), `profile`, `crf`, `tune`, `speed`, `gop` (intra, inter, auto), `order` (none, cluster), `shard_size`, `dedup`, `fps`, `pix_fmt`, `width`. `[media.cluster]`: `space`, `threshold`. `[media.jxl_transcode]`: `verify_roundtrip`, `on_unsupported_jpeg`. `[media.quality]`: the dual gate above.

`[output]` keys: `mode` (single, per-model, both), `embed_media` (the 0x17 blob section), `provenance` (minimal, standard, full), `allow_remote_code`.

## variant naming

sample variants are `<backend>-<knob>-<value>`: `av1-still-s6-crf35`, `av1-auto-dualgate`, `avif-crf35`; `selfcontained-<recipe>` embeds the media in the `.urna`. full-corpus builds are `v03-<profile>` in `candidates/` and `<profile>` under `release/v0.3/`. experiment 11 names encoders `<encoder>-<preset>-<quality>`: `svt-p6-crf35`, `avif-s6-q48`, `x264-crf31`.
