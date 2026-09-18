"""shared plumbing for the bench tools.

repo-relative paths, the urna checkout (URNA_REPO), the spellbook data
root (MTG_DATA, legacy alias SPELLBOOK_DATA) and the jpegtran binary
(JPEGTRAN override, else PATH). every tool imports this instead of
guessing where it sits.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXPERIMENTS = REPO / "benchmark" / "experiments"
CORPORA = REPO / "benchmark" / "corpora"
RUNS = REPO / "benchmark" / "runs"
CANDIDATES = REPO / "candidates"
RELEASE = REPO / "release"
PROFILES = REPO / "profiles"

DATA_VARS = ("MTG_DATA", "SPELLBOOK_DATA")
_VAR = re.compile(r"\$\{(\w+)\}")


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(2)


def urna_repo() -> Path:
    """the urna checkout; URNA_REPO is mandatory, there is no guessed default."""
    raw = os.environ.get("URNA_REPO", "").strip()
    if not raw:
        die("URNA_REPO is not set; export URNA_REPO=/path/to/urna (the hoffresearch/urna checkout)")
    root = Path(os.path.expanduser(raw)).resolve()
    if not (root / "python" / "forge").is_dir():
        die(f"URNA_REPO={root} has no python/forge package; point it at the urna checkout root")
    return root


def add_urna_to_path() -> Path:
    root = urna_repo()
    sys.path.insert(0, str(root / "python"))
    return root


def data_root() -> Path | None:
    """spellbook data root from MTG_DATA (or the legacy SPELLBOOK_DATA); None when unset."""
    for var in DATA_VARS:
        raw = os.environ.get(var, "").strip()
        if raw:
            return Path(os.path.expanduser(raw))
    return None


def require_data_root() -> Path:
    root = data_root()
    if root is None:
        die('MTG_DATA is not set; export MTG_DATA="/path/to/Spellbook/data" (mtg.sqlite + images/)')
    if not (root / "mtg.sqlite").is_file():
        die(f"MTG_DATA={root} has no mtg.sqlite")
    return root


def expand_path(p: str) -> Path:
    """expand ${VAR} and ~ in a manifest or spec path.

    ${MTG_DATA} and ${SPELLBOOK_DATA} are aliases: whichever is exported
    serves both. any other ${VAR} comes from the environment. an unresolved
    placeholder is an error, never a silent literal '$'.
    """
    env = dict(os.environ)
    root = data_root()
    if root is not None:
        for var in DATA_VARS:
            env.setdefault(var, str(root))

    def sub(m: re.Match) -> str:
        name = m.group(1)
        if name not in env:
            die(f"path '{p}' uses ${{{name}}} which is not set; export {name}=... and rerun")
        return env[name]

    out = _VAR.sub(sub, p)
    if out.startswith("~"):
        out = os.path.expanduser(out)
    return Path(out)


def jpegtran() -> str:
    """the jpegtran binary: JPEGTRAN env override, else the first one on PATH."""
    override = os.environ.get("JPEGTRAN", "").strip()
    if override:
        if not Path(override).is_file():
            die(f"JPEGTRAN={override} does not exist")
        return override
    found = shutil.which("jpegtran")
    if not found:
        die("jpegtran not on PATH; install mozjpeg (or libjpeg-turbo) or export JPEGTRAN=/path/to/jpegtran")
    return found


def rel(p: Path) -> str:
    """repo-relative display form for logs and provenance."""
    try:
        return str(p.resolve().relative_to(REPO))
    except ValueError:
        return str(p)
