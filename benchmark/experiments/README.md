# Experiments

One directory per experiment, `NN-slug/`, with a `README.md` (hypothesis, method, verdict), a `results.json` (the numbers) and a `table.md` rendered from it by `benchmark/tools/render_report.py`.

The numbers 01 to 14 follow the sections of the 2026-09-03 report, archived in `docs/archive/results-2026-09-03-pt.md`, so a number here points at the same section there. Three sections measured nothing, and their numbers have no experiment:

| Number | Report section | Where it lives now |
|---|---|---|
| 04 | The recommended default (backend, tune, crf, gop per corpus kind) | The profiles in `profiles/` and the table in the README |
| 07 | The state of the art, a literature pass of 2026-08-31 | `docs/references.md` |
| 12 | The final table, one full-corpus file per row | Experiment 05 and the release table in the README and the dataset card |

Number 03 holds the image-model measurements of 2026-08-31, not the report's section 3 (its conclusions). From 15 on, numbers continue in the order the experiments ran.
