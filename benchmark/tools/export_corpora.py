#!/usr/bin/env python3
"""derive the corpus id lists under benchmark/corpora/ from the evidence on disk.

every list is {"name", "n", "seed", "rule", "derived_from", "ids"}; an id is
the forge item key "img_id|oracle_id" (img_id = basename stem of the card's
image_uri, oracle_id = the card). the lists carry no bytes, only ids, so
anyone with the spellbook sqlite can rebuild the exact samples.

  sample-2048   the forge --sample 2048 rule: rows[int(i * n / 2048)] over the
                38627 rows sorted by (img_id, oracle_id). evenly spaced and
                seed independent (the --seed flag has no effect). read from any
                benchmark/runs/<variant> manifest and cross-checked against the rule.
  sample-1500   the same rule with 1500, from ${MTG_DATA}/mtg.sqlite when set,
                else from the full-corpus manifest order.
  frames-96     numpy default_rng(7).choice(2048, 96, replace=False), sorted
                ordinals of the 2048 sample mapped to keys (measure_variants.py
                and the i-frame battery quality sample).
  queries-100   numpy default_rng(7).choice(38627, 100, replace=False) over the
                full manifest, mapped to keys (urna_model_bench.py --queries 100 --seed 7).
  reprints-2787 printings whose normal/front file exists locally, grouped by
                illustration_id, keeping groups with more than one printing
                (corpus B of 09-inter-ordering). needs the sqlite and the images.
  gate-48       media.crf_auto.sample_indices of the crf40 candidate manifest
                (quality_gate.stratified_sample, deterministic, no rng).

usage (repo root):
  export MTG_DATA="/path/to/Spellbook/data"   # optional for sample-2048/frames-96/queries-100/gate-48
  python3 benchmark/tools/export_corpora.py [--dry-run]
"""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_env as env  # noqa: E402

N_FULL = 38627
SQL_CARDS = (
    "SELECT oracle_id, name, mana_cost, type_line, oracle_text, rarity, set_code, image_uri "
    "FROM cards WHERE image_uri IS NOT NULL"
)
SQL_PRINTINGS = "SELECT oracle_id, illustration_id, image_uri FROM printings WHERE image_uri IS NOT NULL"


def stem(uri: str) -> str:
    return Path(uri.split("?")[0]).stem


def evenly_spaced(rows: list, n: int) -> list:
    """the forge sampling rule (urna python/forge/corpus_sources.py load_rows)."""
    if n >= len(rows):
        return list(rows)
    step = len(rows) / n
    return [rows[int(i * step)] for i in range(n)]


def manifest_keys(path: Path) -> list[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as f:
            items = [json.loads(line) for line in f if line.strip()]
    else:
        items = json.loads(path.read_text())["items"]
    items.sort(key=lambda it: it["ordinal"])
    return [it["key"] for it in items]


def find_full_manifest() -> Path | None:
    cands = sorted(env.CANDIDATES.glob("*/mtgdataset.manifest.json")) if env.CANDIDATES.is_dir() else []
    rel = sorted(env.RELEASE.glob("*/*/items.jsonl.gz")) if env.RELEASE.is_dir() else []
    for p in cands + rel:
        return p
    return None


def find_runs_manifest() -> Path | None:
    for name in ("control", "av1-still-s6-crf35"):
        p = env.RUNS / name / "mtgdataset.manifest.json"
        if p.is_file():
            return p
    hits = sorted(env.RUNS.glob("*/mtgdataset.manifest.json")) if env.RUNS.is_dir() else []
    return hits[0] if hits else None


def sqlite_keys(root: Path) -> list[str]:
    con = sqlite3.connect(f"file:{root / 'mtg.sqlite'}?mode=ro", uri=True)
    rows = [(stem(r[7]), r[0]) for r in con.execute(SQL_CARDS)]
    rows.sort()
    return [f"{img}|{oid}" for img, oid in rows]


def reprints(root: Path) -> tuple[list[str], int]:
    con = sqlite3.connect(f"file:{root / 'mtg.sqlite'}?mode=ro", uri=True)
    front = root / "images" / "normal" / "front"
    local = []
    for oid, ill, uri in con.execute(SQL_PRINTINGS):
        s = stem(uri)
        if (front / s[0] / s[1] / f"{s}.jpg").is_file():
            local.append((s, oid, ill))
    counts: dict[str, int] = {}
    for _, _, ill in local:
        counts[ill] = counts.get(ill, 0) + 1
    keep = sorted((s, oid, ill) for s, oid, ill in local if counts[ill] > 1)
    groups = len({ill for _, _, ill in keep})
    return [f"{s}|{oid}" for s, oid, _ in keep], groups


def doc(name: str, seed, rule: str, derived_from: str, ids: list[str], **extra) -> dict:
    d = {"name": name, "n": len(ids), "seed": seed, "rule": rule, "derived_from": derived_from}
    d.update(extra)
    d["ids"] = ids
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="report the inputs that would be used, write nothing")
    ap.add_argument("--out", type=Path, default=env.CORPORA)
    args = ap.parse_args()
    root = env.data_root()
    runs_manifest = find_runs_manifest()
    full_manifest = find_full_manifest()
    crf40 = env.CANDIDATES / "v03-retrieval" / "mtgdataset.manifest.json"
    print(f"data root: {root or 'unset'}")
    print(f"runs manifest: {env.rel(runs_manifest) if runs_manifest else 'none'}")
    print(f"full manifest: {env.rel(full_manifest) if full_manifest else 'none'}")
    print(f"crf40 candidate manifest: {'present' if crf40.is_file() else 'absent'}")
    if args.dry_run:
        return 0
    if root and (root / "mtg.sqlite").is_file():
        full_keys = sqlite_keys(root)
        full_from = "${MTG_DATA}/mtg.sqlite, cards WHERE image_uri IS NOT NULL, sorted by (img_id, oracle_id)"
    elif full_manifest:
        full_keys = manifest_keys(full_manifest)
        full_from = f"{env.rel(full_manifest)} items[] in ordinal order"
    else:
        env.die("need MTG_DATA (mtg.sqlite) or a full-corpus manifest under candidates/ or release/")
    if len(full_keys) != N_FULL:
        env.die(f"expected {N_FULL} full-corpus keys, got {len(full_keys)}")
    if full_manifest and root:
        mk = manifest_keys(full_manifest)
        if mk != full_keys:
            env.die("sqlite order and full manifest order disagree; refusing to export")
        print(f"full manifest order matches the sqlite rule ({len(mk)} keys)")

    args.out.mkdir(parents=True, exist_ok=True)
    written = []

    # sample-2048: from the runs manifest, verified against the rule
    rule_2048 = evenly_spaced(full_keys, 2048)
    if runs_manifest:
        keys_2048 = manifest_keys(runs_manifest)
        if keys_2048 != rule_2048:
            env.die(f"{env.rel(runs_manifest)} keys do not follow the evenly spaced rule")
        print(f"sample-2048: {env.rel(runs_manifest)} matches rows[int(i * {N_FULL} / 2048)] for all 2048 keys")
        from_2048 = f"{env.rel(runs_manifest)} items[].key, verified equal to the rule over the full row order"
    else:
        keys_2048 = rule_2048
        from_2048 = "the rule over the full row order (no runs manifest on disk to cross-check)"
    written.append(
        doc(
            "sample-2048",
            None,
            f"rows[int(i * {N_FULL} / 2048)] for i in range(2048) over rows sorted by (img_id, oracle_id); "
            "this is urna build --sample 2048 (forge corpus_sources.load_rows), evenly spaced, the --seed flag has no effect",
            from_2048,
            keys_2048,
        )
    )

    # sample-1500
    written.append(
        doc(
            "sample-1500",
            None,
            f"rows[int(i * {N_FULL} / 1500)] for i in range(1500) over rows sorted by (img_id, oracle_id); "
            "this is urna build --sample 1500 (the five-model verification build of 03-image-models)",
            full_from,
            evenly_spaced(full_keys, 1500),
        )
    )

    # frames-96 and queries-100 need numpy's generator to reproduce the exact draws
    try:
        import numpy as np
    except ImportError:
        env.die("numpy is required for frames-96 and queries-100 (default_rng(7).choice)")
    idx96 = sorted(np.random.default_rng(7).choice(len(keys_2048), size=96, replace=False).tolist())
    written.append(
        doc(
            "frames-96",
            7,
            "sorted(numpy.random.default_rng(7).choice(2048, size=96, replace=False)) as ordinals of sample-2048, mapped to keys "
            "(measure_variants.py SAMPLE_N=96 SEED=7; the i-frame battery reuses the same draw)",
            "sample-2048 ordinals",
            [keys_2048[i] for i in idx96],
            ordinals=idx96,
        )
    )
    idx100 = sorted(np.random.default_rng(7).choice(N_FULL, size=100, replace=False).tolist())
    written.append(
        doc(
            "queries-100",
            7,
            f"sorted(numpy.random.default_rng(7).choice({N_FULL}, size=100, replace=False)) as ordinals of the full corpus, mapped to keys "
            "(urna python/tools/urna_model_bench.py pick_items with --queries 100 --seed 7; items filtered to those with image_path, which is all of them)",
            full_from,
            [full_keys[i] for i in idx100],
            ordinals=idx100,
        )
    )

    # gate-48 from the crf40 candidate manifest
    if crf40.is_file():
        m = json.loads(crf40.read_text())
        idx = m["media"]["crf_auto"]["sample_indices"]
        keys = {it["ordinal"]: it["key"] for it in m["items"]}
        written.append(
            doc(
                "gate-48",
                None,
                "forge quality_gate.stratified_sample: items bucketed by (resolution, entropy, has_text), per sorted bucket members[::max(1, len // 12)][:12]; deterministic, no rng",
                "candidates/v03-retrieval/mtgdataset.manifest.json media.crf_auto.sample_indices mapped through items[].ordinal",
                [keys[i] for i in idx],
                ordinals=list(idx),
                buckets=m["media"]["crf_auto"]["buckets"],
            )
        )
    else:
        print("gate-48: skipped, crf40 candidate manifest absent")

    # reprints-2787 from sqlite + local files
    if root and (root / "images" / "normal" / "front").is_dir():
        ids, groups = reprints(root)
        written.append(
            doc(
                "reprints-2787",
                None,
                "printings WHERE image_uri IS NOT NULL, kept when ${MTG_DATA}/images/normal/front/{s[0]}/{s[1]}/{s}.jpg exists for s = basename_stem(image_uri), "
                "then kept when the illustration_id occurs more than once among those; id = stem|oracle_id, sorted",
                "${MTG_DATA}/mtg.sqlite printings table plus the local normal/front files",
                ids,
                groups=groups,
            )
        )
        print(f"reprints: {len(ids)} printings in {groups} illustration groups")
    else:
        print("reprints-2787: skipped, needs MTG_DATA with images/normal/front")

    for d in written:
        path = args.out / f"{d['name']}.json"
        path.write_text(json.dumps(d, indent=1) + "\n")
        print(f"written: {env.rel(path)} (n={d['n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
