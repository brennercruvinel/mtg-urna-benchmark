# contributing

the repository is small on purpose: exact numbers in json, prose in the readmes, and one script that renders both into `RESULTS.md`. a contribution is usually a new experiment directory or a correction to one.

## adding an experiment

create `benchmark/experiments/NN-slug/` with the next free number and a short slug. it needs a `results.json` that follows the contract below, a `README.md` with three lines that start with `hypothesis:`, `method:` and `verdict:` (each on a single line, that is what the renderer reads), and optionally `specs/` for the toml files and `samples/` for small encoded samples. heavy artifacts (`.urna`, media, caches) stay out of git and go to the hugging face dataset.

## the results.json contract

```
{
  "experiment": "NN-slug",                  must equal the directory name
  "title": "...",
  "provenance": {"status": "measured" | "transcribed", "source": "...", "date": "...", "notes": "..."},
  "constants": {"source_bytes": 3975063106},       optional row-level fallbacks
  "tables": [{"title": "...", "columns": [...], "rows": [{...}], "notes": ["..."]}],
  "notes": ["..."]                                  optional, after the tables
}
```

bytes are stored as integers; MB and GB exist only at render time (decimal, 1e6 and 1e9). a column is `{"key", "label", "fmt", "from", "num", "den"}` with fmt one of str, int, f1 to f9, mb, gb, ratio and pct_change. `measured` means the numbers were read from artifacts or sidecars on disk; `transcribed` means they were copied from a report whose artifacts are gone, and the provenance notes say which.

## before committing

run `python3 benchmark/tools/render_report.py` to regenerate `RESULTS.md` and every `table.md`, then `python3 benchmark/tools/render_report.py --check`, which must print `up to date`. that check is the ci gate.

no tracked file may name a machine: use `${MTG_DATA}` for the spellbook data root, `${URNA_REPO}` for the urna checkout, `${XDG_CACHE_HOME:-~/.cache}/urna` for caches and repo-relative paths elsewhere. `benchmark/tools/sanitize_sidecars.py` rewrites sidecars that came out of the forge.

prose is english and lowercase, acronyms and unit symbols in caps (MB, GB, HNSW where it is an acronym in a sentence). no emoji, no em dash character (use a comma, a colon or a plain hyphen), straight quotes. commit messages are short and plain, no conventional-commits prefix, no attribution trailers.
