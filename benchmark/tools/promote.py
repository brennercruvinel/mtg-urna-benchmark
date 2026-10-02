#!/usr/bin/env python3
"""promote a validated candidate build to release/<version>/<profile>/.

what a release dir holds:
  mtgdataset.urna    the artifact itself (gitignored, hosted on hugging face)
  build.lock.json    the forge build lock (packages, tools, models, resolved spec)
  manifest.json      the forge manifest with items[] stripped
  items.jsonl.gz     the stripped items[], one json object per line (gitignored)
  SHA256SUMS         sha256 of the .urna and of every sidecar above
  CITATION_KEY       identity of the file, read from the .urna with `urna inspect --json`;
                     built_with is the urna that built the file (kept from an existing key,
                     or given with --built-with: the sidecars do not record it), read_with
                     the urna that read it

subcommands:
  promote  <candidate-dir> <version> <profile> [--built-with "urna X.Y.Z"] [--dry-run] [--force]
           validates the candidate (urna validate, the manifest's item count against the
           file's chunks), copies the .urna, strips the manifest, writes the sums and the
           key, then checks the result. refuses to overwrite a release dir unless --force.
  check    <release-dir> [...]         verify SHA256SUMS, and the file_hash and content_hash
                                       in CITATION_KEY against the file.
  strip    <manifest.json> <out-dir>   only the manifest split (used to convert
           legacy release sidecars in place).
  key      <file.urna> [out] [--built-with ...]  only CITATION_KEY (stdout when out is omitted).
  sums     <release-dir>               rewrite SHA256SUMS for an existing release dir.

the candidate dir is what the forge wrote: <name>.urna, <name>.manifest.json,
<name>.build.lock.json. `urna` must be on PATH (or URNA_BIN set).

usage (repo root):
  python3 benchmark/tools/promote.py promote candidates/v03-retrieval-crf50 v0.3 retrieval --dry-run
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_env as env  # noqa: E402

URNA_NAME = "mtgdataset.urna"
SIDECARS = ("build.lock.json", "manifest.json", "items.jsonl.gz")
KEY_FIELDS = ("content_hash", "file_hash", "chunker_version", "title", "n_chunks")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def urna_bin() -> str:
    b = os.environ.get("URNA_BIN") or shutil.which("urna")
    if not b:
        env.die("urna cli not found; put it on PATH or export URNA_BIN=/path/to/urna")
    return b


def inspect(urna: Path) -> dict:
    r = subprocess.run([urna_bin(), "inspect", "--json", str(urna)], capture_output=True, text=True)
    if r.returncode != 0:
        env.die(f"urna inspect failed on {env.rel(urna)}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout)


def urna_version() -> str:
    r = subprocess.run([urna_bin(), "--version"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def validate(urna: Path) -> None:
    r = subprocess.run([urna_bin(), "validate", str(urna)], capture_output=True, text=True)
    if r.returncode != 0:
        env.die(f"urna validate failed on {env.rel(urna)}: {(r.stdout + r.stderr).strip()[-300:]}")


def existing_built_with(key_path: Path) -> str | None:
    if not key_path.is_file():
        return None
    for line in key_path.read_text().splitlines():
        if line.startswith("built_with = "):
            return line.split(" = ", 1)[1].strip()
    return None


def citation_key(urna: Path, built_with: str) -> str:
    info = inspect(urna)
    man = info.get("manifest", {})
    values = {
        "content_hash": info.get("content_hash"),
        "file_hash": info.get("file_hash"),
        "chunker_version": man.get("chunker_version"),
        "title": man.get("title"),
        "n_chunks": info.get("n_chunks", man.get("n_chunks")),
    }
    missing = [k for k in KEY_FIELDS if values[k] in (None, "")]
    if missing:
        env.die(f"urna inspect did not report {missing} for {env.rel(urna)}")
    lines = [f"{k} = {values[k]}" for k in KEY_FIELDS]
    lines.append(f"built_with = {built_with}")
    lines.append(f"read_with = {urna_version()} inspect --json")
    return "\n".join(lines) + "\n"


def check(release_dir: Path) -> bool:
    """SHA256SUMS against the files, and CITATION_KEY against the file it names."""
    ok = True
    sums = release_dir / "SHA256SUMS"
    if not sums.is_file():
        print(f"{env.rel(release_dir)}: no SHA256SUMS")
        return False
    for line in sums.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        p = release_dir / name.strip()
        if not p.is_file():
            print(f"  missing {name}")
            ok = False
        elif sha256(p) != digest:
            print(f"  {name}: sha256 differs from SHA256SUMS")
            ok = False
    urna = release_dir / URNA_NAME
    key = (release_dir / "CITATION_KEY").read_text() if (release_dir / "CITATION_KEY").is_file() else ""
    if urna.is_file():
        info = inspect(urna)
        for field in ("file_hash", "content_hash"):
            if f"{field} = {info.get(field)}" not in key:
                print(f"  CITATION_KEY {field} differs from the file ({info.get(field)})")
                ok = False
    print(f"{env.rel(release_dir)}: {'ok' if ok else 'MISMATCH'}")
    return ok


def strip_manifest(src: Path, out_dir: Path, dry_run: bool = False) -> tuple[int, int]:
    """write out_dir/manifest.json (items[] replaced by a pointer) and items.jsonl.gz."""
    doc = json.loads(src.read_text())
    items = doc.pop("items", [])
    doc["items"] = {
        "stripped_to": "items.jsonl.gz",
        "n": len(items),
        "fields": sorted({k for it in items[:1] for k in it}),
    }
    if dry_run:
        return len(items), 0
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    with gzip.open(out_dir / "items.jsonl.gz", "wt", compresslevel=9) as f:
        for it in items:
            f.write(json.dumps(it, sort_keys=True) + "\n")
    return len(items), (out_dir / "items.jsonl.gz").stat().st_size


def write_sums(release_dir: Path) -> str:
    lines = []
    for name in (URNA_NAME, *SIDECARS):
        p = release_dir / name
        if p.is_file():
            lines.append(f"{sha256(p)}  {name}")
    text = "\n".join(lines) + "\n"
    (release_dir / "SHA256SUMS").write_text(text)
    return text


def candidate_files(cand: Path) -> tuple[Path, Path, Path]:
    urnas = sorted(cand.glob("*.urna"))
    if len(urnas) != 1:
        env.die(f"{env.rel(cand)}: expected exactly one .urna, found {len(urnas)}")
    urna = urnas[0]
    stem = urna.stem
    manifest = cand / f"{stem}.manifest.json"
    lock = cand / f"{stem}.build.lock.json"
    for p in (manifest, lock):
        if not p.is_file():
            env.die(f"{env.rel(cand)}: missing {p.name}")
    return urna, manifest, lock


def cmd_promote(args) -> int:
    cand = Path(args.candidate)
    urna, manifest, lock = candidate_files(cand)
    dest = env.RELEASE / args.version / args.profile
    if dest.exists() and any(dest.iterdir()) and not args.force:
        env.die(f"{env.rel(dest)} exists and is not empty; pass --force to overwrite")
    validate(urna)
    info = inspect(urna)
    n_chunks = info.get("n_chunks")
    n_items, _ = strip_manifest(manifest, dest, dry_run=True)
    if n_chunks is not None and n_items != n_chunks:
        env.die(f"{manifest.name} lists {n_items} items, the file holds {n_chunks} chunks")
    built_with = existing_built_with(dest / "CITATION_KEY") or args.built_with
    if not built_with:
        env.die('pass --built-with "urna X.Y.Z": the sidecars do not record the urna that built the file')
    print(f"candidate: {env.rel(cand)}")
    print(f"  urna: {urna.name} {urna.stat().st_size} bytes, content_hash {info.get('content_hash')}")
    print(
        f"  title: {info.get('manifest', {}).get('title')}; chunker {info.get('manifest', {}).get('chunker_version')}"
    )
    print(f"  manifest: {manifest.name} ({manifest.stat().st_size} bytes, {n_items} items to strip)")
    print(f"destination: {env.rel(dest)}")
    print("  files: " + ", ".join((URNA_NAME, *SIDECARS, "SHA256SUMS", "CITATION_KEY")))
    if args.dry_run:
        print("dry run: nothing written")
        print("CITATION_KEY would read:")
        print(citation_key(urna, built_with), end="")
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(urna, dest / URNA_NAME)
    shutil.copy2(lock, dest / "build.lock.json")
    strip_manifest(manifest, dest)
    (dest / "CITATION_KEY").write_text(citation_key(dest / URNA_NAME, built_with))
    write_sums(dest)
    print(f"promoted to {env.rel(dest)}")
    return 0 if check(dest) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("promote", help="candidate dir -> release/<version>/<profile>")
    p.add_argument("candidate")
    p.add_argument("version")
    p.add_argument("profile")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--built-with", help='the urna that built the file, e.g. "urna 0.5.1"; kept from an existing key')
    c = sub.add_parser("check", help="verify release dirs against SHA256SUMS and CITATION_KEY")
    c.add_argument("release_dirs", nargs="+")
    s = sub.add_parser("strip", help="split a manifest into manifest.json + items.jsonl.gz")
    s.add_argument("manifest")
    s.add_argument("out_dir")
    k = sub.add_parser("key", help="print or write CITATION_KEY for a .urna")
    k.add_argument("urna")
    k.add_argument("out", nargs="?")
    k.add_argument("--built-with", help="the urna that built the file; kept from an existing key at out")
    m = sub.add_parser("sums", help="rewrite SHA256SUMS of a release dir")
    m.add_argument("release_dir")
    args = ap.parse_args()
    if args.cmd == "promote":
        return cmd_promote(args)
    if args.cmd == "strip":
        n, size = strip_manifest(Path(args.manifest), Path(args.out_dir))
        print(f"stripped {n} items into {env.rel(Path(args.out_dir) / 'items.jsonl.gz')} ({size} bytes)")
        return 0
    if args.cmd == "check":
        return 0 if all([check(Path(d)) for d in args.release_dirs]) else 1
    if args.cmd == "key":
        built_with = (existing_built_with(Path(args.out)) if args.out else None) or args.built_with
        if not built_with:
            env.die('pass --built-with "urna X.Y.Z": the sidecars do not record the urna that built the file')
        text = citation_key(Path(args.urna), built_with)
        if args.out:
            Path(args.out).write_text(text)
            print(f"written: {env.rel(Path(args.out))}")
        else:
            print(text, end="")
        return 0
    if args.cmd == "sums":
        print(write_sums(Path(args.release_dir)), end="")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
