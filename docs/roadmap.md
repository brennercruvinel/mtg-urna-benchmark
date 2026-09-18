# roadmap

the open items after v0.3, each with what is missing and why it matters. the order is roughly the order I would do them in. every item ends with an issue line that the publish step fills.

## a hit@k floor for the retrieval-only gate

done on 2026-09-12. urna pull request #135 adds a hit@1 utility floor to the crf=auto gate and a `retrieval-auto` profile that walks the ladder on utility alone; experiment 14 measured the seven full-corpus files at n=1000 and put the edge of the clip ruler between crf50 and crf55. what remains is the ruler itself: clip tops out near 0.09 hit@1 on this corpus, and experiment 15 measures the models that read the printed name.

issue: https://github.com/brennercruvinel/mtg-urna-benchmark/issues/1

## wemm and jina over crf50 media

done on 2026-09-12, experiment 15: three builds of the same 512-card sample (lossless, crf35, crf50) with clip, siglip2, jina-v5-omni-nano and wemm-2b, 200 text queries each. no model loses txt@1 at crf50 beyond noise (siglip2 0.93, wemm-2b 0.91 on a file 7.3x smaller than lossless), and the text readers are the ones that drift least in cosine. the crf50 retrieval recipe is safe for them on this sample; a sharper test needs the full corpus or a name-collision slice.

issue: https://github.com/brennercruvinel/mtg-urna-benchmark/issues/2

## avif q48 as the stills backend

done on 2026-09-12, urna pull request #137: `profile = "stills"` now resolves to one avif per image (libaom q48, speed 8) and the old recipe stays as `stills-av1`. two things came out after the switch, both on 2026-09-13: the read path was paying libpng's deflate on every avif decode (experiment 17; urna #138 writes the intermediate uncompressed, 94 to 32 ms per card), and libaom writes different bytes with one worker than with two or more (experiment 18; urna #139 pins `-j 8` and records it, since avifenc's default tied the file_hash to the core count of the build machine). the stills release on the hub is still the av1 stream; a rebuild under the avif profile is the next release cut.

issue: https://github.com/brennercruvinel/mtg-urna-benchmark/issues/3

## recalibrate the dual-gate floors, or extend the ladder below 30

done on 2026-09-12, urna pull request #137: the defaults moved to ssim2 p10 60, min 45, drift 0.95 and the ladder to 25..50, the values the 2048-card sample reaches (crf30 passes, crf35 fails on p10), so `crf = "auto"` picks a rung on this corpus class instead of falling back with a warning. what is still open is the gate model: every profile gates on clip, the model that reads the art and not the name, and the retrieval-auto profile should gate on siglip2 or wemm with a larger sample than the 48 stratified items. that needs the gpu and follows the five-model build.

issue: https://github.com/brennercruvinel/mtg-urna-benchmark/issues/4

## rebuild the v0.3 releases under the mtgdataset name

done on 2026-09-12. the two release files carried `chunker_version = spellbook/1`, the title "Spellbook MTG corpus" and `media://spellbook-*` uris inside, while the sidecars beside them said mtgdataset/1 because they were renamed after the build; that is why the releases had content_hash c993ceda against cb8fdf8f for the candidates, and why the release build lock did not reproduce the file it described. both were rebuilt from `profiles/archive.toml` and `profiles/neardup.toml` with the forge at main: archive 3,606,342,844 bytes, file_hash `sha256:882427094aa6035aa1ddf6abd26444f1598345fb9be3a66612f50b99be377eeb`; neardup 1,374,447,548 bytes, file_hash `sha256:071233c549f45644a3ce9a3bc581e0fe564ed30f70a01b30f726efb3b5c50132`; both content_hash `sha256:cb8fdf8f13fa50f93969de7603386f1c2b117a5e4946c60ac9894a3c5a1f062b` and chunker mtgdataset/1, media bytes identical to the old builds. the c993ceda twins were replaced on disk and on hugging face.

issue: https://github.com/brennercruvinel/mtg-urna-benchmark/issues/5

## the avif source_bytes fix and the candidate manifest

done on 2026-09-12. the avif backend of the urna forge summed its letterboxed png intermediates as source_bytes, so the avif candidate manifest recorded 21,450,566,470 bytes of source and a ratio of 18.61 for a 3,975,063,106-byte jpeg corpus. urna pull request #132 passes the real source size into encode_avif and records the png sum as `letterboxed_input_bytes`; the candidate manifest on disk and on hugging face was patched by hand the same day (source_bytes 3,975,063,106, ratio 3.45, a `patched` note in the media block). what remains is cosmetic: a rebuild of the avif candidate with the fixed forge would make its lock reproduce the manifest without the hand patch.

issue: https://github.com/brennercruvinel/mtg-urna-benchmark/issues/6

## the five-model full build and the model pins

done on 2026-09-14: `release/v0.3/stills-5models`, 35 hours on an m4, and experiment 20 measured it with every card as a query (siglip2 0.750, wemm-2b 0.744 at rank 1). what stays open from this item: the gate still measures with clip, and the utility floor of urna #135 should run with siglip2 on this file; the art-series rows (2,246 cards with no printed name) should be a corpus list of their own so a name-retrieval number can be reported with and without them; wemm-4b and wemm-9b stay unpinned and unmeasured.

issue: https://github.com/brennercruvinel/mtg-urna-benchmark/issues/7

## research notes

three of the five measured on 2026-09-13, experiment 16. the phash prefilter is refuted on this corpus: the same-illustration pairs sit at a median hamming of 28 bits out of 64 because most of them are a framed printing next to a borderless one, the same art at another scale, which is also why grouping bought experiment 09 so little. the binary index with int8 rescoring holds: on siglip2 a hamming top-200 over 96-byte rows keeps 0.93 of the exact top-10 and top-800 keeps 0.97, the int8 ladder's own ceiling; the same measurement puts the int8 ladder itself at 0.92 recall@10 on clip, which is the int8 confound of the dataset card measured on image-to-image neighbours. the golden frame is a null result on groups of two. crf search by a metric target is experiment 19. av2 and cool-chic stay unmeasured: no encoder on this machine writes a stream the forge decodes.

issue: https://github.com/brennercruvinel/mtg-urna-benchmark/issues/8

## hygiene

three candidates sit in `candidates/` and should be promoted or discarded. making `tune=still` the schema default invalidates every embed cache keyed on the media recipe, so it needs a deliberate cut. the full-corpus manifest is 13 MB of `items[]` and provenance `minimal` would drop most of it; the release sidecars already strip `items[]` into `items.jsonl.gz`, the candidates do not.

issue: https://github.com/brennercruvinel/mtg-urna-benchmark/issues/9

## a reprint corpus that has reprints in it

only one image per oracle_id is on disk (38,630 files). the printings table has 100,367 printings with an image_uri, 65,000 of them never downloaded, and the 2787 "reprints" on disk are mostly framed-versus-borderless pairs. the near-dup profile, the gop probe and the golden frame have nothing to measure until the other printings exist locally, about 7 GB from scryfall. that download is a decision for the owner, not a build step.

issue: none yet

## an in-process decoder for the read path

experiment 17: 23 of the 27 ms a single card costs from the av1 stream is ffmpeg starting up, and the batched path walks every frame between the first and the last hit, so for hits spread over the corpus it loses to k single seeks by a factor of six. a dav1d binding (or pyav) in the forge read path removes the spawn and makes `decode_frames_at` choose between a walk and k seeks by the span. upstream work in urna, measured here.

issue: none yet
