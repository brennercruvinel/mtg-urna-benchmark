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

every list whose ids index the card order (all but reprints-2787) records the
keys_hash of the full 38627-key order it was drawn from: sha256 over each
key plus a newline, in ordinal order, the keys_hash sources/sources.toml pins
for the published snapshot. a derivation from any other order is refused.

every list is validated before anything is written (n, unique ids, ids in the
card order, ordinals mapping to their ids), and the files are replaced
atomically, all or none.

--check writes nothing: it reads the card order from a release items.jsonl.gz
(--items, a local release/, else the pinned hub revision), requires its
keys_hash to be the pin, re-derives sample-2048, sample-1500, frames-96 and
queries-100 and compares them with the tracked files, and checks gate-48 and
reprints-2787 structurally (gate-48 is re-derived when its candidate manifest
is on disk). it needs no MTG_DATA, so it runs in CI.

usage (repo root):
  export MTG_DATA="/path/to/Spellbook/data"   # optional for sample-2048/frames-96/queries-100/gate-48
  python3 benchmark/tools/export_corpora.py [--dry-run]
  python3 benchmark/tools/export_corpora.py --check [--items release/v0.3/stills/items.jsonl.gz]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_env as env  # noqa: E402

N_FULL = 38627
SOURCES = env.REPO / "sources" / "sources.toml"
HUB_ITEMS = "release/v0.3/stills/items.jsonl.gz"
DETERMINISTIC = ("sample-2048", "sample-1500", "frames-96", "queries-100")
CARD_ORDER = DETERMINISTIC + ("gate-48",)
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


def doc(name: str, seed, rule: str, derived_from: str, ids: list[str], keys_hash: str | None = None, **extra) -> dict:
    d = {"name": name, "n": len(ids), "seed": seed, "rule": rule, "derived_from": derived_from}
    if keys_hash:
        d["keys_hash"] = keys_hash
    d.update(extra)
    d["ids"] = ids
    return d


def keys_hash(keys: list[str]) -> str:
    """sha256 over each key plus a newline, in order: prepare_from_hub's keys_hash."""
    h = hashlib.sha256()
    for k in keys:
        h.update(k.encode() + b"\n")
    return "sha256:" + h.hexdigest()


def snapshot_pin() -> dict:
    return tomllib.loads(SOURCES.read_text())["snapshot"]


def derive(full_keys: list[str]) -> dict[str, tuple[list[str], list[int] | None]]:
    """the four lists that follow from the card order alone: name -> (ids, ordinals)."""
    import numpy as np

    s2048 = evenly_spaced(full_keys, 2048)
    i96 = sorted(np.random.default_rng(7).choice(len(s2048), size=96, replace=False).tolist())
    i100 = sorted(np.random.default_rng(7).choice(len(full_keys), size=100, replace=False).tolist())
    return {
        "sample-2048": (s2048, None),
        "sample-1500": (evenly_spaced(full_keys, 1500), None),
        "frames-96": ([s2048[i] for i in i96], i96),
        "queries-100": ([full_keys[i] for i in i100], i100),
    }


def problems(d: dict, full_keys: list[str], kh: str) -> list[str]:
    """what is wrong with one list, given the card order and its keys_hash; empty when sound."""
    name, ids = d.get("name"), d.get("ids") or []
    out = []
    if d.get("n") != len(ids):
        out.append(f"n is {d.get('n')}, ids has {len(ids)}")
    if len(set(ids)) != len(ids):
        out.append("ids repeat")
    if name == "reprints-2787":
        if ids != sorted(ids):
            out.append("ids are not sorted")
        if not isinstance(d.get("groups"), int):
            out.append("no groups count")
        return out
    if d.get("keys_hash") != kh:
        out.append(f"keys_hash is {d.get('keys_hash')}, the card order is {kh}")
    known = set(full_keys)
    if any(i not in known for i in ids):
        out.append("ids outside the card order")
    ords = d.get("ordinals")
    if name in ("queries-100", "gate-48"):
        if ords is None or any(not 0 <= o < len(full_keys) for o in ords) or ids != [full_keys[o] for o in ords]:
            out.append("ordinals do not map to the ids through the card order")
    if name == "frames-96":
        s2048 = evenly_spaced(full_keys, 2048)
        if ords is None or any(not 0 <= o < 2048 for o in ords) or ids != [s2048[o] for o in ords]:
            out.append("ordinals do not map to the ids through sample-2048")
    return out


def write_all(docs: list[dict], out: Path) -> None:
    """every file to a temporary beside its target first, then all renamed: all or none."""
    out.mkdir(parents=True, exist_ok=True)
    staged = []
    for d in docs:
        tmp = out / f".{d['name']}.json.tmp"
        tmp.write_text(json.dumps(d, indent=1) + "\n")
        staged.append((tmp, out / f"{d['name']}.json"))
    for tmp, path in staged:
        os.replace(tmp, path)
        print(f"written: {env.rel(path)} (n={json.loads(path.read_text())['n']})")


def card_order_for_check(items: Path | None) -> tuple[list[str], str]:
    if items is None:
        local = sorted(env.RELEASE.glob("*/*/items.jsonl.gz")) if env.RELEASE.is_dir() else []
        items = local[0] if local else None
    if items is None:
        from huggingface_hub import hf_hub_download

        pin = snapshot_pin()
        items = Path(hf_hub_download(pin["repo"], HUB_ITEMS, repo_type="dataset", revision=pin["revision"]))
        where = f"{pin['repo']}@{pin['revision'][:12]}:{HUB_ITEMS}"
    else:
        where = env.rel(items)
    return manifest_keys(items), where


def check(out: Path, items: Path | None) -> int:
    full_keys, where = card_order_for_check(items)
    kh, pin = keys_hash(full_keys), snapshot_pin()
    print(f"card order: {where}, {len(full_keys)} keys, keys_hash {kh}")
    failed = []
    if len(full_keys) != N_FULL or kh != pin["keys_hash"]:
        env.die(f"the card order is not the pinned one: {len(full_keys)} keys, keys_hash {kh}, pin {pin['keys_hash']}")
    derived = derive(full_keys)
    crf40 = env.CANDIDATES / "v03-retrieval" / "mtgdataset.manifest.json"
    for path in sorted(out.glob("*.json")):
        d = json.loads(path.read_text())
        bad = problems(d, full_keys, kh)
        name = d.get("name")
        how = "structural"
        if name in derived:
            ids, ords = derived[name]
            how = "re-derived"
            if d.get("ids") != ids or (ords is not None and d.get("ordinals") != ords):
                bad.append("differs from its re-derivation over the card order")
        elif name == "gate-48" and crf40.is_file():
            m = json.loads(crf40.read_text())
            keys = {it["ordinal"]: it["key"] for it in m["items"]}
            how = "re-derived from the crf40 candidate manifest"
            if d.get("ids") != [keys[i] for i in m["media"]["crf_auto"]["sample_indices"]]:
                bad.append("differs from the crf40 candidate manifest")
        print(f"{name}: {'ok' if not bad else 'FAIL'} ({how}){''.join('; ' + b for b in bad)}")
        if bad:
            failed.append(name)
    missing = sorted(set(CARD_ORDER + ("reprints-2787",)) - {json.loads(p.read_text()).get("name") for p in out.glob("*.json")})
    if missing:
        failed.extend(missing)
        print(f"missing lists: {', '.join(missing)}")
    if failed:
        env.die(f"{len(failed)} corpus list(s) failed: {', '.join(failed)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="report the inputs that would be used, write nothing")
    ap.add_argument("--out", type=Path, default=env.CORPORA)
    ap.add_argument("--check", action="store_true", help="verify the tracked lists against the pinned card order, write nothing")
    ap.add_argument("--items", type=Path, help="items.jsonl.gz of a release, for --check (default: local release, else the hub)")
    args = ap.parse_args()
    if args.check:
        return check(args.out, args.items)
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
    kh = keys_hash(full_keys)
    if kh != snapshot_pin()["keys_hash"]:
        env.die(f"the card order has keys_hash {kh}, not the published snapshot's {snapshot_pin()['keys_hash']}; refusing to export")

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
            keys_hash=kh,
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
            keys_hash=kh,
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
            keys_hash=kh,
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
            keys_hash=kh,
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
                keys_hash=kh,
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

    bad = {d["name"]: problems(d, full_keys, kh) for d in written}
    bad = {k: v for k, v in bad.items() if v}
    if bad:
        env.die("refusing to write: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in bad.items()))
    write_all(written, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
