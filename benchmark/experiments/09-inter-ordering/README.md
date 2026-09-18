# 09 inter ordering

2026-08-31. the similarity lever, measured on a corpus where the similarity is real and on one where it is not.

hypothesis: the more visual similarity between neighbouring frames, the more inter prediction saves; on same-artwork reprints the saving is large, on unique cards it is small, and the earlier +18% of experiment 02 was an artifact of scene-cut detection and of comparing against an intra stream that had tune=still.
method: two corpora, all rows av1 crf35 speed 6 yuv420; corpus A is the 2048 unique cards, corpus B is 2787 printings of the same artwork in 1359 illustration_id groups (source 245.7 MB); intra without tune as the base, inter with scene-cut detection off in source order and in semantic order, gop of one keyframe, 8, 16 and 32, grouped by art against shuffled, and low-delay with tune iq; bytes at a fixed crf, no quality column.
verdict: confirmed on bytes and quantified: inter gop 16 grouped is -29% against intra on corpus B, gop 16 beats a single keyframe (85.0 vs 95.0 MB) while keeping random access within 16 decoded frames; on corpus A inter with scd=0 in semantic order ties tune=still at -18.3%; grouped and shuffled differ by 1.8 MB on corpus B, so part of the gain is the chrome every card shares and not the repeated art; tune iq and inter do not stack, svt-av1 accepts iq only in all-intra or low-delay and low-delay costs +21%.

the caveat that the matrix cannot show: it compares bytes without a quality column. the forge probe later measured inter at crf35 losing about 16 ssimulacra2 points on unique cards, which is why the near-dup profile vetoes inter per segment when quality drops beyond a 2-point tolerance. product fallout: gop=inter emits keyint=16 with scene-cut detection off (INTER_KEYINT in the urna forge) and the probe became quality-aware.

provenance: transcribed from section 9 of the 2026-09-03 report; bytes are the MB figures times 1e6. the encoded artifacts were not kept and no script survives; corpus B membership is reproducible from `benchmark/corpora/reprints-2787.json`.
