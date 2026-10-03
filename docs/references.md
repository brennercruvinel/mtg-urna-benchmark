# references

what the benchmark leans on, grouped by the question each group answers. the list is the one the maintainer supplied; the paragraphs say why each entry is here.

## set redundancy and album coding

the compression lever of experiment 09 has a name and a lineage, and the lossless ceiling of experiment 08 has a published challenger.

karadimitriou, k. "set redundancy, the enhanced compression model, and methods for compressing sets of similar images". phd thesis, louisiana state university, 1996. the term set redundancy comes from here: the information shared across a collection that a single-image codec cannot exploit. the urna forge's `order=cluster` plus `gop=inter` is one way to spend it.

wu, h., sun, x., yang, j., zeng, w., wu, f. "lossless compression of jpeg coded photo collections". ieee transactions on image processing, 2016. https://www.microsoft.com/en-us/research/?p=265095

this paper is the one to take seriously against experiment 08. it reports more than 31% lossless savings on jpeg photo collections by treating the collection as a pseudo-video and predicting in the dct domain, that is, without decoding to pixels. our battery found the byte-reversible ceiling at 1.12x (jxl-transcode) and found that lossless video in the pixel domain loses by 3.3 to 3.8x, which is consistent with the paper's own argument: the pixel domain is the wrong place to look. there is no open implementation of the dct-domain method, and none of the tools we had (cjxl, ffv1, x264, webp) does it. so the ceiling stated in this repository is the ceiling with available tools, and this paper is the reference anyone must beat or reproduce before calling the ceiling general. I would not be surprised if a reimplementation on card scans, which share a frame and a text box across the whole set, did better than 31%.

corsini, m., et al. "image sets compression via patch redundancy". euvip 2019. https://vcg.isti.cnr.it/Publications/2019/CBPC19. patch-level redundancy across a set, a middle ground between per-image coding and pseudo-video.

## neural codecs

ladune, t., et al. "cool-chic: coordinate-based low complexity hierarchical image codec". iccv 2023. paper: https://openaccess.thecvf.com/content/ICCV2023/papers/Ladune_COOL-CHIC_Coordinate-based_Low_Complexity_Hierarchical_Image_Codec_ICCV_2023_paper.pdf. code: https://github.com/Orange-OpenSource/Cool-Chic. the neural codec candidate for a spike because it is the one with a c decoder that runs on cpu; the 2024 video variant has an inter module relevant to near-duplicate corpora.

compressai. https://github.com/InterDigitalInc/CompressAI. the reference library for learned image compression baselines, if a neural row ever enters the intra battery.

## codecs and tools

svt-av1. https://gitlab.com/AOMediaCodec/SVT-AV1. the av1 encoder behind every av1 row (4.2.0 via ffmpeg 9). tune=3 is the still-picture tune (iq); presets 10 and 12 map to the same all-intra stream.

libaom. https://aomedia.googlesource.com/aom. the av1 encoder behind avifenc; out-compresses svt-av1 all-intra by 12.4% at matched quality on this corpus (experiment 11).

libavif. https://github.com/AOMediaCodec/libavif. avifenc 1.4.2 with aom 3.14.1.

libjxl. https://github.com/libjxl/libjxl. cjxl 0.12.0; `--lossless_jpeg=1` is the byte-reversible transcode of the archive profile.

ab-av1. https://github.com/alexheretic/ab-av1. crf search by target vmaf; the sibling of the forge's `crf=auto`, and the precedent for the metric-target search on the roadmap.

vvenc. https://github.com/fraunhoferhhi/vvenc. vvc intra at 100x the cost of x264 for a mid-table size (experiment 11).

## metrics

ssimulacra2. https://github.com/cloudinary/ssimulacra2. the fidelity axis of every quality number here; the calibration target of experiment 11 is a mean of 61.96.

vmaf. https://github.com/Netflix/vmaf. not used, listed because ab-av1 targets it and a video-oriented reader will ask.

bd-rate (bjontegaard delta). the standard summary of one rate-distortion curve against another. four calibrated points per codec would let experiment 11 report it.

## coding for machines

image and video coding for machines (icm and vcm) is the standards name for compression judged by a downstream task instead of by a human viewer; the mpeg vcm exploration (iso/iec jtc 1/sc 29/wg 2, 2019 onward) and the jpeg ai call for proposals frame the rate-utility trade-off that experiment 13 measures with hit@k. the observation that a fidelity or feature-drift metric does not predict task accuracy is recurrent in that literature; this repository confirms it on one corpus and does not claim it.

## containers

lance. https://github.com/lancedb/lance. the closest relative of the `.urna`: blob semantics, vectors, full text search. a lance dataset is a directory of fragments; a `.urna` is one file.

webdataset. https://github.com/webdataset/webdataset. tar shards for training pipelines, no search.

ffcv. https://github.com/libffcv/ffcv. training-oriented dataset format, no search.

sqlite-vec. https://github.com/asg017/sqlite-vec. single-file vectors inside sqlite, brute force, no media.

usearch. https://github.com/unum-cloud/usearch and hnswlib https://github.com/nmslib/hnswlib. the ann engines the urna runtime is benchmarked against elsewhere; here they matter as the reference for what an hnsw section is.

## dedup

imagededup. https://github.com/idealo/imagededup and fastdup https://github.com/visual-layer/fastdup. the phash-to-cnn cascade on the roadmap; the raw cache has 38 md5 duplicate groups, so byte dedup is not where the redundancy is.

## public benchmarks and datasets

clic. https://compression.cc. the learned image compression challenge; the convention of reporting rate-distortion at matched quality.

kodak. https://r0k.us/graphics/kodak/. the classic 24-image set every codec paper reports on.

the cloudinary codec comparisons by jon sneyers, with ssimulacra2 as the quality axis, are the precedent for the quality-matched bytes of experiment 11.

beir. https://github.com/beir-cellar/beir and mteb https://github.com/embeddings-benchmark/mteb. the hit@k protocol references for the utility layer: fixed query set, fixed k, ground truth declared.

scryfall bulk data. https://scryfall.com/docs/api/bulk-data. the source of the cards, the printings and the image urls.
