# 03 image models

2026-08-31. five models on a 1500-card sample, the same three rulers on each, never added up.

hypothesis: the image models differ far more in what they read from a card than in how they tolerate the codec, so identity, drift and text-to-image utility have to be reported as three numbers, and a model that reads the printed name will beat clip on the name query by a wide margin.
method: urna build --spec specs/mtgdataset-1500.toml --sample 1500 with potion, clip-vit-b32, siglip2, jina-v5-omni-nano@256 and wemm-2b@256; urna_model_bench.py with 60 seeded queries, t1 identity@1 from the source image, t2 drift p10 between source and decoded-frame embeddings, t3 txt@k with the ruler "artwork of the card {name}" against each model's own image space; embed throughput in items per second on apple silicon mps fp16.
verdict: confirmed. identity@1 is 1.000 for all four image models; drift p10 runs from 0.967 (clip) to 0.990 (wemm); txt@1 goes from 0.233 (clip, which sees only the art) to 0.933 (wemm-2b sliced to 256 of 2048 dims), with siglip2 at 0.850 and jina at 0.617; the models that read the printed text find the exact card by its name, and the cost is throughput, 0.6 and 0.3 items per second against clip's 17.

the crf auto gate refused the entire [30..45] ladder on this build and fell back to crf30, which is why the media is 81 MB for 1500 cards. the full 38,627-card five-model build was never run; wemm-2b alone was estimated at 18 to 20 hours.

provenance: transcribed. the 1500x5 verification .urna was lost when a temp dir was cleaned; the numbers come from the urna changelog (unreleased section) and the 2026-09-11 dossier. the sample itself is reproducible: `benchmark/corpora/sample-1500.json`.
