#!/usr/bin/env python3
"""Give a published candidate the sidecars a release has, without renaming what is published.

A release dir carries mtgdataset.urna, manifest.json (items stripped to
items.jsonl.gz), build.lock.json, SHA256SUMS and CITATION_KEY. The candidates
on the hub carry only the .urna and the forge's mtgdataset.manifest.json and
mtgdataset.build.lock.json, and their items were dropped (or point at an
items.jsonl.gz that was never uploaded). This writes, into --out:

  items.jsonl.gz              the release's rows (key, label, image_path, ordinal),
                              with each media_uri read from the candidate's own file:
                              an exact search over every chunk returns its blob uri
                              and span with the 0x16 overlay applied
  mtgdataset.manifest.json    only when its items entry is the old `items_stripped`
                              note: replaced by the release form {stripped_to, n, fields}
  CITATION_KEY                as promote.py writes it; built_with is taken from a
                              release whose file has the same file_hash, else given
                              with --built-with, else `unrecorded`
  SHA256SUMS                  the .urna, both forge sidecars and items.jsonl.gz

Refused before anything is written: a candidate whose chunk order or
corpus_input_hash differs from the release's, or whose media uris do not
cover every chunk. Needs a checkout of urna (URNA_REPO).

usage (repo root):
  python3 benchmark/tools/candidate_sidecars.py candidates/v03-retrieval-crf55 \\
      --release release/v0.3/retrieval --out staging/v03-retrieval-crf55
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_env as env  # noqa: E402

URNA = "mtgdataset.urna"
MANIFEST = "mtgdataset.manifest.json"
LOCK = "mtgdataset.build.lock.json"
ITEMS = "items.jsonl.gz"
FIELDS = ["image_path", "key", "label", "media_uri", "ordinal"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def release_items(release: Path) -> list[dict]:
    with gzip.open(release / ITEMS, "rt") as f:
        items = [json.loads(line) for line in f if line.strip()]
    items.sort(key=lambda it: it["ordinal"])
    if [it["ordinal"] for it in items] != list(range(len(items))):
        env.die(f"{env.rel(release / ITEMS)}: ordinals are not 0..n-1")
    return items


def media_uris(db, n: int) -> list[str]:
    """The media_uri of every chunk in file order, from the spans the file stores."""
    hits = db.search([1.0] + [0.0] * (db.embedding_dim - 1), k=n)
    by_id = {h.chunk_id: h for h in hits}
    out = []
    for cid in db.chunk_ids():
        h = by_id.get(cid)
        if h is None or not h.source_uri.startswith("media://"):
            env.die(f"chunk {cid} has no media span in the file")
        out.append(
            f"{h.source_uri}#frame={h.offset_start}"
            if "#" not in h.source_uri and h.source_uri.endswith(".mp4")
            else h.source_uri
        )
    return out


def items_bytes(rows: list[dict], uris: list[str]) -> bytes:
    """gzip with mtime 0 and the release's line form, so equal rows give equal bytes."""
    text = "".join(json.dumps(dict(r, media_uri=u), sort_keys=True) + "\n" for r, u in zip(rows, uris, strict=True))
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, filename="") as g:
        g.write(text.encode())
    return buf.getvalue()


def normalized_manifest(manifest: dict, n: int) -> dict | None:
    """The manifest with the release's items entry, or None when it already has it."""
    items = manifest.get("items")
    if isinstance(items, dict) and items.get("stripped_to") == ITEMS and items.get("n") == n:
        return None
    if "items_stripped" not in manifest and not (isinstance(items, dict) and items.get("stripped_to")):
        env.die("the manifest has neither the release items entry nor the old items_stripped note")
    out = {k: v for k, v in manifest.items() if k != "items_stripped"}
    out["items"] = {"fields": FIELDS, "n": n, "stripped_to": ITEMS}
    return out


def built_with_for(file_hash: str, given: str | None, release_root: Path) -> str:
    if given:
        return given
    for key in sorted(release_root.glob("*/*/CITATION_KEY")):
        fields = dict(line.split(" = ", 1) for line in key.read_text().splitlines() if " = " in line)
        if fields.get("file_hash") == file_hash and fields.get("built_with"):
            return fields["built_with"]
    return "unrecorded"


def citation_key(info: dict, built_with: str) -> str:
    m = info.get("manifest", {})
    lines = [
        f"content_hash = {info['content_hash']}",
        f"file_hash = {info['file_hash']}",
        f"chunker_version = {m.get('chunker_version') or info.get('chunker_version')}",
        f"title = {m.get('title') or info.get('title')}",
        f"n_chunks = {info['n_chunks']}",
        f"built_with = {built_with}",
        "read_with = urna inspect --json",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidate", type=Path, help="dir with mtgdataset.urna and the forge sidecars")
    ap.add_argument(
        "--release", type=Path, required=True, help="a release dir of the same corpus (items.jsonl.gz, manifest.json)"
    )
    ap.add_argument("--out", type=Path, required=True, help="where the new and changed sidecars are written")
    ap.add_argument("--built-with", help="the forge version, when no release file shares the file_hash")
    args = ap.parse_args()

    cand = args.candidate
    for name in (URNA, MANIFEST, LOCK):
        if not (cand / name).is_file():
            env.die(f"{env.rel(cand / name)} missing")
    if args.out.exists() and any(args.out.iterdir()):
        env.die(f"{env.rel(args.out)} is not empty")
    env.add_urna_to_path()
    import urna

    db = urna.open(str(cand / URNA))
    info = db.inspect()
    n = info["n_chunks"]
    rows = release_items(args.release)
    manifest = json.loads((cand / MANIFEST).read_text())
    rel_manifest = json.loads((args.release / "manifest.json").read_text())
    if len(rows) != n:
        env.die(f"the release lists {len(rows)} items, the candidate holds {n} chunks")
    if manifest.get("corpus_input_hash") != rel_manifest.get("corpus_input_hash"):
        env.die("the candidate's corpus_input_hash differs from the release's")
    ref = urna.open(str(args.release / URNA)).chunk_ids() if (args.release / URNA).is_file() else None
    if ref is not None and db.chunk_ids() != ref:
        env.die("the candidate's chunk order differs from the release's")
    uris = media_uris(db, n)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / ITEMS).write_bytes(items_bytes(rows, uris))
    new_manifest = normalized_manifest(manifest, n)
    manifest_path = cand / MANIFEST
    if new_manifest is not None:
        manifest_path = args.out / MANIFEST
        manifest_path.write_text(json.dumps(new_manifest, indent=1, sort_keys=True) + "\n")
    built = built_with_for(info["file_hash"], args.built_with, env.RELEASE)
    (args.out / "CITATION_KEY").write_text(citation_key(info, built))
    digests = {
        URNA: info["file_hash"].removeprefix("sha256:"),
        LOCK: sha256(cand / LOCK),
        MANIFEST: sha256(manifest_path),
        ITEMS: sha256(args.out / ITEMS),
    }
    (args.out / "SHA256SUMS").write_text("".join(f"{d}  {name}\n" for name, d in sorted(digests.items())))
    changed = "rewritten" if new_manifest is not None else "unchanged"
    print(f"{env.rel(args.out)}: items {n}, manifest {changed}, built_with {built}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
