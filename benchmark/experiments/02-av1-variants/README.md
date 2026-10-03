# 02 av1 variants

2026-08-31. fifteen builds of the same 2048 cards, one toml each under `specs/`, to isolate what each knob of the av1 backend costs and buys.

hypothesis: the v0.2 recipe (crf35, speed 8, default tune) was a poor point on the quality-per-byte curve, and fps, inter prediction, semantic ordering and the dual gate each move bytes or quality in a way that can be isolated by changing one key at a time.
method: urna build --spec with --sample 2048 for each variant, then measure_variants.py: media bytes on disk, urna bytes, encode seconds from the manifest, and on the fixed 96-frame sample (default_rng(7)) ssimulacra2 of the letterboxed source against the decoded frame plus clip cosine drift; lossless classes asserted by sha256 round-trip (bytes) or by the codec's own decoder (pixels).
verdict: tune=still is the upgrade, +10.9 ssim2 p50 (51.8 to 62.7) for +10% bytes at the same crf; fps changes nothing (fps30 intra is byte-identical to still-s6); inter with the old probe costs +18% bytes at lower quality on unique cards; cluster ordering was applied and the probe chose intra, so it cost time and nothing else; the dual gate refused the whole [30..45] ladder and fell back to crf30; avif at "crf35" is another point of the curve (5.48x at p10 34) and not comparable at the same number; embedding the media in the .urna costs 3.0% over the media.

the jxl rows score ssim2 92.8 on a bit-exact transcode because pil and djxl round the same jpeg differently; the reversibility is verified by 2048 of 2048 sha256 round-trips in the build. selfcontained-neardup in measurements.json is the pre-fix probe build (inter chosen on bytes alone, ssim2 p50 46.8); the file now under `benchmark/runs/` is the post-fix rebuild, intra on all four segments, 73,127,600 bytes.

provenance: measured; the media directories were pruned after measurement, the .urna, manifest and build lock of every run remain under `benchmark/runs/`. the avif rows carry a manifest source_bytes of 1,138,810,355 (the letterboxed png intermediates, a forge bug); the ratio column uses the jpeg source.
