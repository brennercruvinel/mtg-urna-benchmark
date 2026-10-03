# changelog

the format follows keep a changelog. versions are those of the `.urna` releases under `release/`.

## [unreleased]

### fixed, 2026-10-03

- `CITATION.cff` said the citation key of a specific `.urna` file is its content_hash. The releases share one content_hash (`cb8fdf8f`), so it cannot name a file: a specific file is its file_hash, listed in `SHA256SUMS`, and the content_hash is what a `urna://` citation resolves in any of them. `CITATION_KEY` already recorded both.

### changed, 2026-10-03 (readme and card)

- the README has the commands to rebuild the source data from the pinned snapshot (`uv sync`, `prepare_from_hub.py`), to check a release from the hub (`hf download --repo-type dataset`, `shasum -c SHA256SUMS`, `promote.py check`) and to search it, with the two searches kept apart: a text query on the potion space (`urna retrieve`) and text-to-image through a model's text tower (`bench_full_corpus.py --preset siglip2`, offline, from the snapshot pinned to `timm/ViT-B-16-SigLIP2@eee10eff`, with the urna loader of #271 and #273, no `refs/main`). `docs/environment.md` names that revision, the five files, the `transformers` dependency, and that clip still resolves `refs/main`. The dataset card gets the same commands (its `hf download` lacked `--repo-type dataset`), the `queries` and `qrels` configs, the candidate sidecars and the siglip2 weights' source; it said any urna after 0.4.0 reads the files, a version with no tag, now 0.5.0 and later.

### added, 2026-10-03 (queries)

- the query lists of experiments 14 and 15 are tracked: `queries-1000` (14), `sample-512` and `queries-200` (15), derived by `export_corpora.py` with the card order's keys_hash and covered by `--check`; the identity blocks of 14 and 15 point at them. no run saved its per-query list, so these, like `queries-100`, are the draw of the rule `urna_model_bench.py` applies.
- `benchmark/tools/export_queries.py` writes the `queries` and `qrels` tables for Hugging Face from the tracked lists plus every card (experiment 20): 39927 queries, each "artwork of the card {label}" with exactly one relevant row, the card itself, which is the benchmark's own evaluation (hit@k, no graded relevance). `gallery` says whether a query ran against the full corpus or the 512-card sample, `art_series` marks the 2246 "name // name" rows experiment 20 reports apart. `benchmark/tests/test_export_queries.py` (4 tests).

### fixed, 2026-10-03 (sidecars)

- the release sidecars tracked here had drifted from the published ones: the nest to urna rename (2026-09-17) rewrote `"mtgdataset.nest"` to `"mtgdataset.urna"` in the `outputs` of each `manifest.json` and `built_with = nest 0.3.0` to `urna 0.3.0` in each `CITATION_KEY`, while `SHA256SUMS` kept the original digests, so every tracked `manifest.json` failed its own `SHA256SUMS` and the files claimed a build tool that did not build them. the ten files are restored byte for byte from the Hugging Face copies, which had stayed consistent; `promote.py check-tracked` verifies every tracked file `SHA256SUMS` lists, and CI runs it on `release/v0.3/*/`.
- the five candidates on the hub had no `SHA256SUMS`, no `CITATION_KEY` and no items: three manifests carried the old `items_stripped` note ("regenerate it with nest build"), and crf55 and crf60 pointed at an `items.jsonl.gz` that was never uploaded. `benchmark/tools/candidate_sidecars.py` writes the missing sidecars without renaming what is published: `items.jsonl.gz` with the release's rows and each `media_uri` read from the candidate's own file (an exact search over every chunk returns its blob span), the manifest's items entry in the release form when it had the old note, `CITATION_KEY` and `SHA256SUMS`. it refuses a candidate whose chunk order or corpus_input_hash differs from the release's. crf50's items come out byte-equal, decompressed, to the published items of the retrieval release, and all five dirs pass `promote.py check` (now aware of the forge's `mtgdataset.*` names) and the evaluator's reader. `built_with` is `nest 0.3.0` for crf50, which is the retrieval release's file (same sha256 `73f814b7`), and `unrecorded` for the other four: their build locks do not name the forge version.
- `release/v0.3/candidates.json` records each candidate's sidecar digests and `built_with`, and `same_file_as` for crf50. `benchmark/tests/test_candidate_sidecars.py` (11 tests) covers the item bytes, the manifest rewrite, `built_with`, the key fields and both checks.

### changed, 2026-10-03 (export)

- `export_corpora.py` records in every list that indexes the card order (all but reprints-2787) the `keys_hash` of that order, the one `sources/sources.toml` pins; the five tracked lists carry it now, their ids unchanged. it validates every list before writing (n, unique ids, ids in the card order, ordinals mapping to ids), refuses a card order that is not the pinned one, and replaces the files all or none. `--check` verifies the tracked lists without `MTG_DATA`: the card order from a release `items.jsonl.gz` (local, or the pinned hub revision), the four rule-derived lists re-derived and compared, gate-48 and reprints-2787 checked structurally. it passes on the tracked lists with the order of both the hub `stills` release and the local `stills-5models` one; CI runs it. `benchmark/tests/test_export_corpora.py` (10 tests) covers the refusals on a synthetic order.

### changed, 2026-10-03

- CI runs the unit tests: `uv sync --locked` installs the base dependencies from `uv.lock`, then `python -m unittest discover -s benchmark/tests` (39 tests; the integration and real-release cases skip without a downloaded release and urna). ruff now checks `benchmark/` (tools and tests) instead of `benchmark/tools` alone. `export_corpora.py --check` runs after the tests.

### changed, 2026-10-02

- the profiles name the forge a checkout of hoffresearch/urna at v0.5.0 or later. the v0.4.0 tag the 2026-09-17 entry names no longer exists in the urna repository (its tags are v0.3.0, v0.5.0, v0.5.1), so v0.5.0 is the first tag that carries the spec features; the `stills-5models` header still said `nest build`, now `urna build`. the files already built keep what they record: `built_with` in each `CITATION_KEY`, the `NEST` magic, `chunker_version` and titles.
- `MTG_DATA` is the one data-root variable; the `SPELLBOOK_DATA` alias is gone from `_bench_env.py`. `sanitize_sidecars.py` still rewrites `${SPELLBOOK_DATA}` in old sidecars; none under `release/` carries it.

### changed, 2026-09-17

- the forge the specs need is a release now: urna v0.4.0 (the tag that carries #131 to #141). `profiles/*.toml` and the readme name the tag instead of a pull request; the hub card names it in the build section.

### added, 2026-09-14 and 15

- `data/cards-*.parquet` on the hub (4.0 GB, 8 shards): the corpus as one row per card with the scan as an image column, the text fields, an `art_series` flag and the ordinal that maps to every release; the hub viewer renders it. tool `benchmark/tools/export_parquet.py`, written from the release's `items.jsonl.gz`.
- `release/v0.3/stills-5models/`: the 38,627-card build with potion, clip, siglip2, jina-v5-omni-nano@256 and wemm-2b@256, the first full-corpus file with the models that read the printed name. stills media, file_hash `6b2bc21a`, 1.44 GB, on the hub. built in 35 hours on an m4 (21 of them wemm-2b at 1.0 image per second).
- experiment 20: hit@k with every card as a query on that file. siglip2 0.750, wemm-2b 0.744, jina 0.336, clip 0.098 at rank 1 (intervals of 0.005). the 512-card numbers were 0.93 and 0.91; 2,246 art-series rows (full art, no printed name, `name // name` labels) take 61% of the misses, and with them out of the gallery plain queries score 0.88 and 0.87. tool `bench_full_corpus.py`.
- the hub card rewritten around the five-model file: file_hash as the identifier, the hit@k table in front, the clip ladder second, the findings of experiments 16 to 19 in the limits.

### added, 2026-09-13

- experiment 16: three of the five research notes measured on the cpu. phash prefilter refuted (the reprint pairs are framed vs borderless printings), binary index with int8 rescoring holds (siglip2 top-200 keeps 0.93 of the exact top-10; the int8 ladder itself is at 0.92 on clip), golden frame null. tools `phash_prefilter.py`, `binary_rescoring.py`, `golden_frame.py`.
- experiment 17: random access per media backend through the forge read path. all-intra av1 is the cheapest read at 27 ms (23 ms is the ffmpeg process start); avif 94 to 32 ms and jxl-transcode 43 to 16 ms after urna #138. tool `measure_latency.py`.
- experiment 18: encoder determinism per worker count. svt-av1 and cjxl byte-identical; libaom with one worker is its own byte class, fixed upstream in urna #139. tool `encoder_determinism.py`.
- experiment 19: the four forge recipes at the same ssimulacra2. the still tune is worth 21.6%; avif speed 6 is 5.0% smaller than the av1 still stream and avif speed 8, the urna #137 stills profile, 1.1% larger: the 13% behind #137 compared files 4.6 points apart. tool `crf_for_target.py`, urna issue #143.
- roadmap: issues #3, #4 and #8 closed with evidence; two new items (a reprint corpus that has reprints in it, an in-process decoder for the read path, urna issue #142).

### upstream, 2026-09-13

- urna #138: `decode_frames_at` bounded to the hit span (it raised on every batched resolve over the real stream), uncompressed avif and ppm jxl intermediates on the read path.
- urna #139: the avif backend pins `avifenc -j 8` and records it.
- urna #140 (open): `tune = "still"` as the av1 default. urna #141 (open): compact manifest items under `provenance = "minimal"`.

- license: MIT for the repository, CC BY 4.0 for the `.urna` artifacts on hugging face; the dataset went public on 2026-09-12.
experiment 15 (text-reading models over crf) landed: hypothesis refuted, no model loses txt@1 at crf50 on 512 cards and the text readers drift least. the 38k five-model build is queued.

## [0.3.2] - 2026-09-12

### added

- `release/v0.3/stills/` and `release/v0.3/retrieval/`: every profile now has a release. stills is a single av1 crf35 stream (1,374,431,484 bytes, file_hash 6f12cadb..., media 1,335,047,579, 14 kB under neardup since there is no clustering); retrieval is the crf50 candidate promoted as is (532,671,548 bytes, file_hash 73f814b7...). both carry content_hash cb8fdf8f.
- candidates `v03-retrieval-crf55` (370,108,284 bytes) and `v03-retrieval-crf60` (229,972,284 bytes), on the hub under `candidates/`.
- experiment 14, text-to-image utility at n=1000 on seven full-corpus files: crf50 and avif q48 sit within one standard error of lossless, crf55 is 1.5 se under, crf60 is 1.9 se under with identity@1 at 0.971. the edge of the clip ruler is between crf50 and crf55.
- `profiles/stills-5models.toml`: the stills recipe with potion, clip, siglip2, jina-v5-omni-nano and wemm-2b, for the 38k five-model build.

### upstream

- urna pull request #135: a hit@1 utility floor for the crf=auto gate (`utility_floor_hit1`, `utility_queries`, `utility_query_template`, `utility_tol`) and the `retrieval-auto` profile. on a 256-card smoke test the utility leg passes every rung to crf60 while the drift and visual floors would veto from crf45 on.

### removed

- the zenodo descriptor and every doi mention.

## [0.3.1] - 2026-09-12

the two v0.3 releases rebuilt under the mtgdataset name, the same day as 0.3.0. no measurement changed: text, vectors and media bytes are the same as in 0.3.0, what changed is the identity inside the file and the sidecars that describe it.

### changed

- `release/v0.3/archive/mtgdataset.urna` rebuilt from `profiles/archive.toml` with the urna forge at main (after pull requests #131 and #133): 3,606,342,844 bytes (the old file was 3,606,304,124, +38,720), file_hash `sha256:882427094aa6035aa1ddf6abd26444f1598345fb9be3a66612f50b99be377eeb`, content_hash `sha256:cb8fdf8f13fa50f93969de7603386f1c2b117a5e4946c60ac9894a3c5a1f062b`, chunker_version mtgdataset/1. the jxl-transcode media blob is 3,563,328,079 bytes, identical to the old build; media stage 6 min, clip embed 872.7 s.
- `release/v0.3/neardup/mtgdataset.urna` rebuilt from `profiles/neardup.toml`: 1,374,447,548 bytes (the old file was 1,374,447,420, +128), file_hash `sha256:071233c549f45644a3ce9a3bc581e0fe564ed30f70a01b30f726efb3b5c50132`, content_hash cb8fdf8f, chunker_version mtgdataset/1. the av1 media blob is 1,335,061,967 bytes over 19 shards and byte-identical to the old build, the encode is deterministic; rows 27.7 s, media 1649.1 s, clip embed 281.1 s.
- the +38,720 and +128 bytes are the longer title, the chunker string and the `media://mtgdataset-*` uris in place of `media://spellbook-*`. nothing else moved, and the content_hash cb8fdf8f now shared by the two releases and the three candidates of experiment 13 is the proof. the old c993ceda twins were replaced and no longer exist on disk.
- both files validated with `urna validate`, promoted with `promote.py --force` (new build lock, stripped manifest, `SHA256SUMS`, `CITATION_KEY`) and uploaded to the hugging face dataset under `release/v0.3/archive/` and `release/v0.3/neardup/`. the five full-corpus files are now on the hub.
- experiment 05 carries two extra rows, state "release (rebuilt 2026-09-12)", with the new bytes; the historical rows stay because they are what the 2026-09-03 numbers were measured on.
- `profiles/*.toml` and the readme say which forge the specs need: `${VAR}` expansion in spec paths since urna #131, the embed cache under `${XDG_CACHE_HOME:-~/.cache}/urna` since #133, a checkout at or after commit 7dc3cc78.

### fixed

- the avif candidate manifest, which recorded source_bytes 21,450,566,470 and ratio 18.61 (the letterboxed png intermediates), patched by hand after urna #132 landed: source_bytes 3,975,063,106, ratio 3.45, the png sum kept as `letterboxed_input_bytes`, a `patched` note in the media block. on disk and on hugging face.

### upstream

- urna pull requests #131 (`${VAR}` in spec paths and the retrieval media profile), #132 (avif source_bytes), #133 (content-addressed embed cache under xdg) and #134 (this benchmark recorded in the urna changelog) merged on 2026-09-12.

## [0.3.0] - 2026-09-12

the first version of the benchmark as a repository. the measurements are those of 2026-08-31 to 2026-09-03; what changed on 2026-09-12 is the structure and the numbers that were wrong.

### added

- numbered experiment directories under `benchmark/experiments/`, each with a `results.json` (exact bytes, provenance status measured or transcribed) and a readme with hypothesis, method and verdict.
- `benchmark/tools/render_report.py`, which renders `RESULTS.md` and every `table.md` from the json; `--check` is the ci gate.
- the six corpus id lists in `benchmark/corpora/` and `export_corpora.py` to regenerate them from the sqlite.
- four product profiles in `profiles/` (stills, neardup, archive, retrieval) with `${MTG_DATA}` sources.
- `release/v0.3/{neardup,archive}/` with the build lock, the stripped manifest, `SHA256SUMS` and `CITATION_KEY`; `promote.py` produces them from a candidate.
- `sanitize_sidecars.py`, which rewrites the data root and the urna checkout in every sidecar to `${MTG_DATA}` and `${URNA_REPO}` so no tracked file names a machine.
- `docs/`: methodology, hypotheses, references, roadmap, glossary, this changelog, and the 2026-09-03 report archived verbatim with a supersession note.

### changed

- units. bytes are stored exact and MB and GB are decimal (1e6, 1e9). the 2026-09-03 report used `du` output in binary units labelled as GB.
- every full-corpus row shows two ratios, on the `.urna` and on the media blob; the old report mixed the two bases.
- the three self-contained sample variants that measurements.json carried and the old table omitted (selfcontained-neardup, selfcontained-jxl-transcode, selfcontained-avif) are in experiment 02.
- experiment 11 carries all 19 encoder rows, the old table showed 12.

### fixed

unit errors corrected against the 2026-09-11 audit, all in the old report and its tables:

- jxl-transcode e7 is 1.115x (211,018,809 / 189,231,744), not 1.124x; 1.124x is e9. the prose "-11.1%" was e9 at -11.0%; e7 is -10.3%.
- the lossless video rows lose 3.3 to 3.8x against the source jpeg; against jxl-transcode e9 the loss is 3.7 to 4.3x.
- retrieval crf40 is 980,715,452 bytes = 0.981 GB (the report said 0.935 GB, which is MiB), 4.05x on the `.urna` and 4.22x on the media; "-31% vs still" is -27.7% and "-74% vs source" was against the archive.
- retrieval crf50 is 532,671,548 bytes = 0.533 GB (not 0.508), 7.46x on the `.urna` and 8.06x on the media.
- avif q48 is 1,195,973,116 bytes = 1.196 GB (not 1.101, which was the media blob in MiB), 3.32x on the `.urna` and 3.45x on the media; against neardup it is -13.0% on the `.urna`, so the i-frame prediction of -12.4% held and did not "materialize larger".
- the raw cache is 7,201,468,217 bytes (7.201 GB) of images, not "6.9 GB" (GiB from du); art_crop/front is 3.015 GB, not 3.0 GiB.
- "about 2800 orphan images per class" was wrong: those are the 2824 back faces referenced by cards.image_uri_back; the true front orphans are 3 (38,630 stems for 38,627 cards).
- "grouped vs shuffled differ by 1.8 points" in the inter matrix is 1.8 MB; in percentage points against intra it is 1.5.
- the same still build was quoted at 3.02x (media) and 2.93x (urna) in two sections; both are now shown with their base.

seed provenance correction:

- the 2048-card sample is evenly spaced, `rows[int(i * 38627 / 2048)]` over rows sorted by (img_id, oracle_id), and seed independent; the old report said "seed 42". verified 2048 of 2048 keys against the control manifest. the only seeded draws are the 96 quality frames and the 100 utility queries, both `default_rng(7)`.

avif manifest error:

- the avif backend of the urna forge sums its letterboxed png intermediates as source_bytes. the avif candidate manifest therefore says source 21,450,566,470 and ratio 18.61; the sample avif rows say 1,138,810,355. every ratio in the rendered tables uses the jpeg source (3,975,063,106 on the full corpus, 211,018,809 on the sample). the backend fix is a pending pull request in urna and the manifest is regenerated once it lands.

### known

- the two release files carried `chunker_version spellbook/1` inside while the sidecars said mtgdataset/1 (renamed after the build); content_hash c993ceda for the releases, cb8fdf8f for the candidates. closed by the rebuild in 0.3.1.
- experiments 03, 09 and 10 and the utility table of 13 are transcribed: their artifacts were not kept.
