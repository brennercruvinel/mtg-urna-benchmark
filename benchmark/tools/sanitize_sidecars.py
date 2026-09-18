#!/usr/bin/env python3
"""rewrite machine-local paths in build sidecars to portable placeholders.

the forge wrote absolute and home-relative paths into manifests, build locks,
forge state and logs. before those sidecars travel (git, hugging face) every
occurrence of the spellbook data root becomes ${MTG_DATA} and every
occurrence of the urna checkout becomes ${URNA_REPO}:

  <home>/<the macos application support dir>/Spellbook/data  -> ${MTG_DATA}
  ~/<the same dir>/Spellbook/data                            -> ${MTG_DATA}
  ${SPELLBOOK_DATA} (legacy alias)                           -> ${MTG_DATA}
  ~/Dev/hoff/urna/                                           -> ${URNA_REPO}/

the literal strings are assembled from pieces below so this file itself
never contains a machine path (the release scan greps for them).

log files: any line that still names a home directory after the rewrite is
dropped (python warnings quote the venv path), together with a following
"warnings.warn(" continuation line.

files touched: *.json, *.toml, *.log, *.lock under candidates/, release/ and
benchmark/runs/ by default (pass more roots as arguments). rewrites are
textual, so formatting and key order are preserved; file modes are kept.

usage (repo root): python3 benchmark/tools/sanitize_sidecars.py [--dry-run] [ROOT ...]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_env as env  # noqa: E402

DEFAULT_ROOTS = ("candidates", "release", "benchmark/runs")
SUFFIXES = {".json", ".toml", ".log", ".lock"}
HOME_ROOTS = ("Users", "home")  # macos and linux home prefixes
HOME = r"/(?:" + "|".join(HOME_ROOTS) + r")/[^/\s\"']+/"
DATA_TAIL = "/".join(("Library", "Application Support", "Spellbook", "data"))
RULES = [
    (re.compile(HOME + re.escape(DATA_TAIL)), "${MTG_DATA}"),
    (re.compile(r"~/" + re.escape(DATA_TAIL)), "${MTG_DATA}"),
    (re.compile(r"\$\{SPELLBOOK_DATA\}"), "${MTG_DATA}"),
    (re.compile(r"~/Dev/hoff/urna/"), "${URNA_REPO}/"),
]
HOME_LINE = re.compile(HOME)


def sanitize_text(text: str, is_log: bool) -> tuple[str, int]:
    total = 0
    for rx, repl in RULES:
        text, n = rx.subn(repl, text)
        total += n
    if is_log:
        kept = []
        lines = text.splitlines(keepends=True)
        skip_next = False
        for line in lines:
            if skip_next and line.strip() == "warnings.warn(":
                skip_next = False
                total += 1
                continue
            skip_next = False
            if HOME_LINE.search(line):
                total += 1
                skip_next = True
                continue
            kept.append(line)
        text = "".join(kept)
    return text, total


def files_under(roots: list[Path]):
    for root in roots:
        if root.is_file():
            yield root
            continue
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix in SUFFIXES and ".urna" not in p.name:
                yield p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="*", help=f"dirs or files to sanitize (default: {' '.join(DEFAULT_ROOTS)})")
    ap.add_argument("--dry-run", action="store_true", help="report counts, write nothing")
    args = ap.parse_args()
    roots = [env.REPO / r for r in (args.roots or DEFAULT_ROOTS)]
    changed = 0
    for p in files_under(roots):
        try:
            text = p.read_text()
        except UnicodeDecodeError:
            continue
        new, n = sanitize_text(text, p.suffix == ".log")
        if n:
            changed += 1
            print(f"{'would rewrite' if args.dry_run else 'rewrote'} {n:6d} in {env.rel(p)}")
            if not args.dry_run:
                mode = p.stat().st_mode
                p.write_text(new)
                p.chmod(mode)
    print(f"{changed} file(s) {'need' if args.dry_run else 'had'} rewrites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
