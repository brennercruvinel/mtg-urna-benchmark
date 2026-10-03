#!/usr/bin/env bash
# The benchmark from nothing: fresh clones, the hub at a pinned revision, every check.
#
#   sh benchmark/tools/clean_install_proof.sh WORKDIR [MTG_REF] [URNA_REF] [HUB_REV]
#
# WORKDIR must be empty or absent. Defaults: this repo's main, Urna's v0.5.3
# tag and the hub's current main, each resolved to a commit and recorded. Needs git, uv,
# cargo, the hf CLI (from the locked env), ffmpeg with libsvtav1, and macOS
# sandbox-exec for the offline step. Writes WORKDIR/record.json and
# WORKDIR/proof.log; stops at the first failing step, which record.json names.
#
# Steps:
#   1  clone mtg-urna-benchmark and hoffresearch/urna; build the urna CLI and
#      the Python extension from that clone
#   2  uv sync --locked --extra forge; the CI checks (ruff, unit tests,
#      export_corpora --check, promote check-tracked, render_report --check)
#   3  download release/v0.3/stills-5models at HUB_REV into a fresh HF cache;
#      shasum -c SHA256SUMS; promote.py check with the CLI from step 1
#   4  export_queries.py from the clone against the hub's queries/qrels tables
#   5  prepare_from_hub.py into a fresh MTG_DATA (the pinned snapshot; it
#      refuses unless corpus_input_hash equals every release manifest's)
#   6  the stills profile at --sample 512 with potion, built twice with separate
#      embed caches: same file_hash, its keys the tracked sample-512 list, and
#      every chunk a chunk of the release (same canonical text, source_uri,
#      ordinal and chunker_version; the release ids use the pre-rename domain)
#   7  the five siglip2 files at the pinned revision into a fresh HF cache, then
#      the evaluator's integration test under sandbox-exec with the network
#      denied: 20 queries, the model_hash in the file, no refs/main
set -u

W=${1:?usage: clean_install_proof.sh WORKDIR [MTG_REF] [URNA_REF] [HUB_REV]}
MTG_REF=${2:-main}
URNA_REF=${3:-v0.5.3}
HUB=brennercruvinel/mtg-urna-benchmark
SIGLIP_REPO=timm/ViT-B-16-SigLIP2
SIGLIP_REV=eee10eff6dd8cabae2d7f379d4e8cfcd352030aa
SIGLIP_FILES="open_clip_model.safetensors open_clip_config.json tokenizer.json tokenizer_config.json special_tokens_map.json"
REL=release/v0.3/stills-5models

if [ -e "$W" ] && [ -n "$(ls -A "$W")" ]; then
    echo "$W is not empty" >&2
    exit 2
fi
mkdir -p "$W"
W=$(cd "$W" && pwd)
LOG=$W/proof.log
STEPS=$W/steps.tsv
: >"$STEPS"
export UV_PYTHON=3.12
unset URNA_ALLOW_DOWNLOAD URNA_PYTHON

finish() {
    python3 - "$W" "$@" <<'EOF'
import json, sys
from pathlib import Path
w = Path(sys.argv[1])
facts = {}
for line in (w / "facts.tsv").read_text().splitlines() if (w / "facts.tsv").exists() else []:
    k, v = line.split("\t", 1)
    facts[k] = v
steps = [dict(zip(("step", "rc", "seconds"), line.split("\t"))) for line in (w / "steps.tsv").read_text().splitlines()]
for s in steps:
    s["rc"], s["seconds"] = int(s["rc"]), int(s["seconds"])
ok = bool(steps) and all(s["rc"] == 0 for s in steps) and sys.argv[2] == "complete"
(w / "record.json").write_text(json.dumps({"ok": ok, "facts": facts, "steps": steps}, indent=1) + "\n")
print(f"record.json: ok={ok}, {len(steps)} steps")
EOF
}

fact() { printf '%s\t%s\n' "$1" "$2" >>"$W/facts.tsv"; }

step() {
    name=$1
    shift
    echo "== $name" | tee -a "$LOG"
    t0=$(date +%s)
    "$@" >>"$LOG" 2>&1
    rc=$?
    printf '%s\t%s\t%s\n' "$name" "$rc" "$(($(date +%s) - t0))" >>"$STEPS"
    if [ "$rc" -ne 0 ]; then
        echo "FAIL $name (rc $rc), see $LOG" >&2
        finish failed
        exit 1
    fi
}

# 1. clones and the urna build
clone() {
    git clone -q "https://github.com/$1" "$2" && git -C "$2" checkout -q --detach "$3"
}
step clone-mtg clone brennercruvinel/mtg-urna-benchmark "$W/mtg" "$MTG_REF"
step clone-urna clone hoffresearch/urna "$W/urna" "$URNA_REF"
fact mtg_commit "$(git -C "$W/mtg" rev-parse HEAD)"
fact urna_commit "$(git -C "$W/urna" rev-parse HEAD)"
cd "$W/mtg" || exit 1

step uv-sync uv sync --locked --extra forge
PY=$W/mtg/.venv/bin/python
fact python "$($PY -c 'import platform; print(platform.python_version())')"
fact platform "$($PY -c 'import platform; print(platform.platform())')"

build_urna() {
    cd "$W/urna" &&
        cargo build -q --release -p urna &&
        PYO3_PYTHON=$PY cargo build -q --release -p urna-python --features pyo3/extension-module &&
        if [ -f target/release/lib_urna.dylib ]; then cp target/release/lib_urna.dylib python/_urna.so; else cp target/release/lib_urna.so python/_urna.so; fi
}
step build-urna build_urna
cd "$W/mtg" || exit 1
export URNA_REPO=$W/urna URNA_BIN=$W/urna/target/release/urna
fact urna_cli "$($URNA_BIN --version)"

# 2. what CI runs
step ruff uvx ruff check benchmark
step unit-tests "$PY" -m unittest discover -s benchmark/tests
step export-check "$PY" benchmark/tools/export_corpora.py --check
step check-tracked sh -c "for d in release/v0.3/*/; do $PY benchmark/tools/promote.py check-tracked \"\$d\" || exit 1; done"
step render-check "$PY" benchmark/tools/render_report.py --check

# 3. a release from the hub
HUB_REV=${4:-$($PY -c "from huggingface_hub import HfApi; print(HfApi().dataset_info('$HUB').sha)")}
fact hub_revision "$HUB_REV"
export HF_HOME=$W/hf-release
step download-release .venv/bin/hf download "$HUB" --repo-type dataset --revision "$HUB_REV" --include "$REL/*" --local-dir "$W/hub"
step sha256sums sh -c "cd '$W/hub/$REL' && shasum -a 256 -c SHA256SUMS"
step promote-check "$PY" benchmark/tools/promote.py check "$W/hub/$REL"
fact release_file_hash "sha256:$(awk '$2 == "mtgdataset.urna" {print $1}' "$W/hub/$REL/SHA256SUMS")"

# 4. the query tables
step download-queries .venv/bin/hf download "$HUB" --repo-type dataset --revision "$HUB_REV" --include "queries/*" --local-dir "$W/hub"
step export-queries "$PY" benchmark/tools/export_queries.py --items "$W/hub/$REL/items.jsonl.gz" --out "$W/queries"
compare_queries() {
    "$PY" - "$W/queries" "$W/hub/queries" <<'EOF'
import sys
import pyarrow.parquet as pq
for name in ("queries", "qrels"):
    a = pq.read_table(f"{sys.argv[1]}/{name}.parquet")
    b = pq.read_table(f"{sys.argv[2]}/{name}.parquet")
    assert a.equals(b), f"{name}: the clone's table differs from the hub's"
    print(name, a.num_rows, "rows, equal")
EOF
}
step compare-queries compare_queries
fact queries_rows "$("$PY" -c "import pyarrow.parquet as pq; print(pq.read_metadata('$W/queries/queries.parquet').num_rows)")"

# 5. the source data from the pinned snapshot
export MTG_DATA=$W/data HF_HOME=$W/hf-snapshot
step prepare-from-hub "$PY" benchmark/tools/prepare_from_hub.py
fact corpus_input_hash "$("$PY" -c "import json; print(json.load(open('$W/data/prepared.json'))['corpus_input_hash'])")"

# 6. a pinned sample, built twice
build_sample() {
    "$PY" "$W/urna/python/tools/urna_forge.py" --spec profiles/stills.toml --sample 512 --models potion \
        --out-dir "$W/sample-$1" --cache-dir "$W/embed-cache-$1"
}
step sample-build-a build_sample a
step sample-build-b build_sample b
compare_sample() {
    "$PY" - "$W" "$REL" <<'EOF'
import json, sys
from pathlib import Path
w, rel = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(w / "urna" / "python"))
import urna
a, b = (urna.open(str(w / f"sample-{x}" / "mtgdataset.urna")) for x in "ab")
ia, ib = a.inspect(), b.inspect()
assert ia["file_hash"] == ib["file_hash"], "the two sample builds differ"
keys = json.loads((w / "mtg/benchmark/corpora/sample-512.json").read_text())["ids"]
items = json.loads((w / "sample-a" / "mtgdataset.manifest.json").read_text()).get("items")
if not isinstance(items, list):
    import gzip
    with gzip.open(w / "sample-a" / "items.jsonl.gz", "rt") as f:
        items = [json.loads(line) for line in f if line.strip()]
got = [it["key"] for it in sorted(items, key=lambda it: it["ordinal"])]
assert got == keys, "the sample's keys are not benchmark/corpora/sample-512.json"
# a chunk_id hashes (text, source_uri, span, chunker_version) under a domain
# string, item://<corpus>/<key> and (ordinal, ordinal + 1) for a forge row. the
# v0.3 files were written before the rename, under nest:chunk_id:v1 (urna
# docs/CHANGELOG, the rename entry), so the sample's ids are recomputed with the
# release's ordinals and that domain, from the canonical text the sample stores.
import gzip, hashlib, struct
def chunk_id(domain, text, uri, start, end, cv):
    h = hashlib.sha256(domain)
    for part in (text.encode(), uri.encode()):
        h.update(struct.pack("<I", len(part)) + part)
    h.update(struct.pack("<QQ", start, end) + struct.pack("<I", len(cv.encode())) + cv.encode())
    return "sha256:" + h.hexdigest()
assert chunk_id(b"urna:chunk_id:v1\n", "t", "u", 0, 1, "v") == urna.chunk_id("t", "u", 0, 1, "v")
release = urna.open(str(w / "hub" / rel / "mtgdataset.urna"))
full = set(release.chunk_ids())
with gzip.open(w / "hub" / rel / "items.jsonl.gz", "rt") as f:
    rel_ordinal = {d["key"]: d["ordinal"] for d in map(json.loads, f)}
cv = release.inspect()["manifest"]["chunker_version"]
stored = {h.chunk_id: h for h in a.retrieve([1.0] + [0.0] * (a.embedding_dim - 1), k=len(items), candidates=len(items), ef=4 * len(items))}
ids = a.chunk_ids()
for it in items:
    h, uri = stored[ids[it["ordinal"]]], f"item://mtgdataset/{it['key']}"
    assert chunk_id(b"urna:chunk_id:v1\n", h.text, uri, it["ordinal"], it["ordinal"] + 1, cv) == h.chunk_id, it["key"]
    o = rel_ordinal[it["key"]]
    assert chunk_id(b"nest:chunk_id:v1\n", h.text, uri, o, o + 1, cv) in full, f"{it['key']}: no chunk of the release has this text"
print(f"{len(items)} of {len(items)} sample chunks are release chunks: same text, source_uri, ordinal, chunker_version")
print(json.dumps({"file_hash": ia["file_hash"], "content_hash": ia["content_hash"], "n": ia["n_chunks"]}))
(w / "sample.json").write_text(json.dumps({"file_hash": ia["file_hash"], "content_hash": ia["content_hash"], "n": ia["n_chunks"]}))
EOF
}
step compare-sample compare_sample
fact sample_512 "$(cat "$W/sample.json")"

# 7. siglip2 offline
export HF_HOME=$W/hf-siglip
# shellcheck disable=SC2086
step download-siglip2 .venv/bin/hf download "$SIGLIP_REPO" $SIGLIP_FILES --revision "$SIGLIP_REV"
MODEL_DIR=$HF_HOME/hub/models--timm--ViT-B-16-SigLIP2
cache_state() { (cd "$MODEL_DIR" && find . -not -path './blobs*' | sort | tr '\n' ' '); }
fact siglip2_cache_before "$(cache_state)"
offline_eval() {
    sandbox-exec -p '(version 1)(allow default)(deny network*)' \
        env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MTG_EVAL_RELEASE="$W/hub/$REL" \
        "$PY" -m unittest -v benchmark/tests/test_eval_integration.py
}
step siglip2-offline-test offline_eval
offline_run() {
    sandbox-exec -p '(version 1)(allow default)(deny network*)' \
        env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
        "$PY" benchmark/tools/bench_full_corpus.py "$W/hub/$REL/mtgdataset.urna" \
        --preset siglip2 --queries 20 --seed 7 --out "$W/siglip2-q20.json"
}
step siglip2-offline-run offline_run
same_as_recorded() {
    "$PY" - "$W/siglip2-q20.json" benchmark/tests/data/eval-siglip2-stills-5models-q20.json <<'EOF'
import json, sys
got, rec = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))["result"]
for k in ("file_hash", "content_hash", "model_hash", "queries"):
    assert got[k] == rec[k], k
assert got["spaces"]["siglip2"]["hit"] == rec["spaces"]["siglip2"]["hit"], "hit@k differs from the recorded run"
print(json.dumps({"model_hash": got["model_hash"], "hit": {k: v["value"] for k, v in got["spaces"]["siglip2"]["hit"].items()}}))
EOF
}
step siglip2-same-as-recorded same_as_recorded
fact siglip2_q20 "$(same_as_recorded 2>/dev/null)"
fact siglip2_cache_after "$(cache_state)"
no_refs() { [ ! -e "$MODEL_DIR/refs/main" ]; }
step no-refs-main no_refs

finish complete
