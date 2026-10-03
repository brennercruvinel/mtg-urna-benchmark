# 05 full corpus

2026-08-31 to 2026-09-01. the whole corpus, 38,627 cards, one self-contained .urna per row.

hypothesis: the recipes that won on the 2048 sample scale to the full corpus with the same ratios, the single-file overhead stays around 3%, and three builds with different media share one content_hash.
method: urna build --spec for the still, neardup and archive recipes with embed_media = true; sizes read from the files on disk on 2026-09-12, media bytes and timings from the build manifests, content_hash and chunker_version with urna inspect --json; ratio_urna divides the 3,975,063,106-byte source by the whole file and ratio_media by the embedded media blob.
verdict: confirmed on ratios and overhead, with two surprises recorded in the manifests: neardup is 1.374 GB (2.89x on the .urna, 2.98x on media) and its probe vetoed inter on all 19 segments with the reason inter-degrades-quality, so it differs from the still build (1.356 GB, 2.93x) only by tune_resolved and ordering; the archive is 3.606 GB (1.10x on the .urna, 1.12x on media) with 38,627 of 38,627 round-trips verified; the three share content_hash c993ceda; the still build carries tune_resolved 4, the silent ms-ssim fallback of the time, neardup carries 3, the real still-picture tune.

the single-file overhead is 39.4 MB of indexes, text and vectors over the 1.317 GB media blob of the still build, +3.0%. the still build was dropped from the release set once neardup superseded it, and the legacy v0.2 row (58 MB .urna, 38 loose mp4 sidecars, 1.7 GB) survives only as a transcription.

provenance: measured for neardup and archive (`release/v0.3/`), the still row from sidecars kept outside this repository, the v0.2 row transcribed. the release files measured on 2026-09-03 said `spellbook/1` inside and `mtgdataset/1` in their sidecars, which were renamed after the build; both were rebuilt on 2026-09-12 under the mtgdataset name (content_hash cb8fdf8f, media bytes identical) and the table carries the rebuilt rows beside the historical ones.
