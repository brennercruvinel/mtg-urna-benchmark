# methodology

how the numbers in `RESULTS.md` were measured, what each ruler can and cannot say, and the weaknesses I know about.

## three layers, never aggregated

every lossy build is scored on three separate rulers and the three are never folded into one number.

t1 identity. query the index with the source image of an item and check that the item itself comes back at rank 1. this is pipeline stability: it says the frame decoded from the file maps back to the right chunk. identity@1 is 1.000 on every build in this repository, which is the expected value, not a result. a value below 1 would mean a frame alignment bug, and one such bug was found this way (decode_frame assumed fps=1 on random access).

t2 drift. cosine similarity between the embedding of the source image and the embedding of the frame decoded from the file, in the same model. reported as the p10 over the sample. this is the cost of the codec as seen by the model, a stability measure. it is also the floor the `crf=auto` gate enforces (drift_floor_p10 0.98 by default).

t3 utility. hit@k of a text query against the image space, ruler `artwork of the card {name}`, for k in 1 and 5. this is what a user of the file experiences. the label is a weak ground truth: clip sees only the art and does not read the printed name, so its absolute txt@1 is low (0.05 to 0.09 on the full corpus) and only the differences between builds carry information.

the reason for keeping them apart is experiment 13. drift p10 goes from 0.9706 at crf35 to 0.9420 at crf50, a fall any reasonable drift floor rejects, while txt@1 stays flat at 0.07 to 0.09. a single aggregated score would have hidden that.

## what the literature calls this

three names cover what the experiments do, and each one is a pointer to prior work rather than a claim of novelty.

image-set compression, or set-redundancy compression, is karadimitriou's 1996 term for exploiting the redundancy across a collection instead of inside each image. experiment 09 (inter prediction with gop 16 over reprints ordered by clip similarity) is the photo-album coding of the 2010 to 2016 line, an mst or cluster ordering followed by a video codec, done with av1. the caveats are in the experiment: bytes at fixed crf, not quality matched, and part of the gain is the shared card frame. wu, sun, yang, zeng and wu (ieee tip 2016) report more than 31 percent lossless savings on jpeg collections with pseudo-video in the dct domain, which is well past the 1.12x ceiling of experiment 08; that ceiling is the one reachable with available tools, and the paper is what a general claim would have to beat.

rate-quality-utility benchmarking is what experiment 13 does when it keeps fidelity (ssimulacra2), signal stability (embedding cosine drift) and task utility (hit@k) apart. the standards world calls the field image and video coding for machines (icm and vcm) or task-aware compression; that drift does not predict utility is a recurring observation there, so this repository reports it as a confirmation on this corpus, not as a finding of its own.

a retrieval-ready archive is the artifact: codec-compressed media, int8 vectors of two spaces, an hnsw index, bm25, a graph and the source spans in one mmap-able, content-addressed file. the closest relative is lance, which has blob semantics, vectors and full-text search but is a directory of fragments. one file against a directory is the product thesis, and the measured cost of that property is the 3.0 percent single-file overhead of experiment 02.

## quality matched comparison

the all-intra battery (experiment 11) does not compare encoders at equal settings, because a crf of 35 means different things to different encoders. it calibrates each encoder to the same fidelity, ssimulacra2 mean 61.96 with a tolerance of 2 points, and then compares bytes. the anchor is the forge baseline, svt-av1 preset 6 crf 35 tune still, reproduced byte-identically (70,092,669 bytes) before anything else was encoded. x264 landed at crf 31, x265 at crf 32, avif at q48 speed 6 and q52 speed 9, vvenc at qp 22, cjxl lossy at distance 4.0.

the precedent is the cloudinary codec comparisons by jon sneyers, which use ssimulacra2 as the quality axis and read bytes at matched quality. one point per codec is the minimum that makes bytes comparable. four points per codec, spanning the operating range, would turn the table into a bjontegaard delta rate (bd-rate), the standard way to summarize one rate-distortion curve against another. that is a small extension and it is on the roadmap.

## three classes of lossless

the word lossless covers three things that must never be conflated, and experiment 08 keeps them in separate rows.

byte-reversible: the original jpeg bytes are recoverable. jxl-transcode (`cjxl --lossless_jpeg=1`) is the only entry in this class that also saves bytes: 1.115x at effort 7, 1.124x at effort 9, verified by sha256 round-trip on every file at build time and again by `urna validate`.

pixel-exact: a re-save that yields the same decoded pixels from different bytes. jpegtran and jpegoptim are this class; on scryfall's already optimized jpegs they save under 1%.

pixel-domain: the decoded pixels are recompressed by another codec. webp lossless, ffv1 and x264 qp0 are this class and every one of them lands above the jpeg it came from (0.26x to 0.30x), because a lossless coder of decoded pixels has to pay for the quantization noise jpeg already spent bits on.

## the samples

the sample rules are what makes the benchmark reproducible without the artifacts, so they are stated exactly and exported as id lists in `benchmark/corpora/`.

the 2048-card sample is `rows[int(i * 38627 / 2048)] for i in range(2048)` over the rows sorted by (img_id, oracle_id). it is evenly spaced, deterministic and seed independent; the `--seed` flag of the forge has no effect on it. the 2026-09-03 report said "seed 42", which was a provenance error, and the export tool verified the rule against the control manifest, 2048 of 2048 keys. the 1500-card sample of experiment 03 follows the same rule with 1500.

the 96 quality frames are `sorted(numpy.random.default_rng(7).choice(2048, 96, replace=False))` as ordinals of the 2048 sample. this is the only seeded draw in the codec batteries, and experiments 02, 08 and 11 share it.

the 100 utility queries are `sorted(numpy.random.default_rng(7).choice(38627, 100, replace=False))` over the full corpus in manifest order, which is identical across the five full-corpus files.

the 48-item gate sample is the forge's stratified_sample: items bucketed by (resolution, entropy, has_text), then `members[::max(1, len // 12)][:12]` per sorted bucket. deterministic, no rng.

corpus B (2787 reprints in 1359 groups) is every printing with a local normal/front file whose illustration_id occurs more than once among those files.

## units

bytes are stored exact in every `results.json`. MB is bytes / 1e6 and GB is bytes / 1e9, decimal, never MiB or GiB. `du` reports allocated blocks in binary units, which is how the old report ended up with 0.935 GB for a 980,715,452-byte file (that is 935 MiB); the corrections are listed in `docs/changelog.md`.

full-corpus rows carry two ratios against the 3,975,063,106-byte source, both shown: ratio_urna divides by the whole self-contained file and ratio_media by the embedded media blob alone. the two differ by the single-file overhead (3%), and quoting one where the other is expected is how the same still build got reported at 3.02x and 2.93x in two sections of the same document.

## known weaknesses

n=100 does not prove equality. "no detectable utility loss at crf50" means the txt@k differences between five builds are inside the noise of 100 queries with a weak label ruler. it is not evidence that crf50 and lossless retrieve equally, and crf55 and crf60 were never measured on utility at all. a floor for a retrieval-only gate needs a larger n and a better ruler before it can be trusted.

the corpus B matrix of experiment 09 is bytes at a fixed crf, not quality matched. the forge probe later measured inter at crf35 losing about 16 ssimulacra2 points on unique cards, so the 29% has a quality cost that the matrix does not show. the encoded artifacts of that matrix were not kept and no script survives; the numbers are transcribed from the 2026-09-03 report.

the txt@k and drift table of experiment 13 is also transcribed: `urna_model_bench.py` output was not saved. the sizes and the gate ladder in the same section were read from the files and manifests on disk on 2026-09-12.

the jxl rows of experiment 02 score ssimulacra2 92.8 on a byte-exact transcode because pil and djxl round the same jpeg differently. the number is a measurement artifact, the reversibility is verified by hash.

the avif manifests record source_bytes as the letterboxed png intermediates (21,450,566,470 on the full corpus, ratio 18.61), a bug in the avif backend of the urna forge. every ratio in this repository uses the jpeg source instead.
