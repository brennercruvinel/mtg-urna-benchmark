# 10 capcut

2026-08-31. a field observation reproduced programmatically so it could be diagnosed instead of argued about.

hypothesis: speeding the card video up 60x in a video editor and exporting at 30 fps halves the bytes, and that halving is a compression path worth building into the forge.
method: take the still-s6 shard of experiment 02 (70,092,669 bytes, 2048 frames at 1 fps), apply a 60x setpts speed-up and export at 30 fps with the editor's h.264 defaults through ffmpeg, then count bytes and frames of the result.
verdict: refuted as a compression path. the output is 30.2 MB with 1055 frames, -57% bytes: the 30 fps export samples the accelerated timeline and drops 993 of the 2048 cards (48% of the dataset), and what remains is h.264 re-encoded over already compressed material, a generational loss; the legitimate gain the observation pointed at, redundancy between frames, is what experiment 09 delivers without losing a card.

the experiment exposed a real bug on the way: decode_frame assumed fps=1 on random frame access, so the fps30 variants of experiment 02 raised an IndexError at frame 71. fixed in the urna forge, the fps now flows from the manifest to the seek.

provenance: transcribed from section 10 of the 2026-09-03 report. the exported mp4 was not kept and the exact ffmpeg recipe is recorded only in prose; the input shard is still embedded in `benchmark/runs/selfcontained-still-s6/mtgdataset.urna` and `urna media --export` reconstructs it with a hash check.
