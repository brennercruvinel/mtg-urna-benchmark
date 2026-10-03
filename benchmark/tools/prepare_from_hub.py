#!/usr/bin/env python3
"""Rebuild the source data root (MTG_DATA) from the dataset's published Parquet snapshot.

The corpus was built from the Spellbook app's local cache of Scryfall bulk data,
which nobody else can download in the same state. The hub dataset carries the
same 38,627 rows as `data/cards-*.parquet`, each with the JPEG scan, the fields
the text template reads and the scan's SHA-256. This tool turns that snapshot,
at the revision pinned in sources/sources.toml, back into what the profiles read:

  $MTG_DATA/mtg.sqlite                         tables `cards` and `names_localized`
  $MTG_DATA/images/normal/front/a/b/<id>.jpg   one scan per card
  $MTG_DATA/prepared.json                      what was checked, and the result

Checks, all of them fatal:
  - every scan's SHA-256 and size match the row's image_sha256 and image_bytes
  - the row count and the keys in ordinal order match the snapshot pin
  - the corpus_input_hash recomputed the way the urna forge computes it (canonical
    text from the profile template, scan SHA-256, label, chunker_version) equals
    the one in every release manifest: the rebuilt data feeds the forge the exact
    items the v0.3 files were built from

MTG_DATA must be empty or absent: the tool refuses before its first write
rather than overwrite a data root. prepared.json is written last, only when
every check passed, so a data root without it is incomplete or wrong.

usage (repo root):
  export MTG_DATA=/path/to/empty/dir
  python benchmark/tools/prepare_from_hub.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import string
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_env as env  # noqa: E402

SOURCES = env.REPO / "sources" / "sources.toml"
TEXT_FIELDS = ("oracle_id", "name", "mana_cost", "type_line", "oracle_text", "rarity", "set_code")


# render_template and item_input_hash: copied from hoffresearch/urna
# python/forge/corpus_sources.py at 61255194 (MIT), so the recomputed hash is the
# forge's own. A sqlite NULL reaches the template as None, as in the forge.
class _Blank(dict):
    def __missing__(self, key):
        return ""


def render_template(template: str, row: dict) -> str:
    lines = []
    for line in template.strip().splitlines():
        fields = [f for _, f, _, _ in string.Formatter().parse(line) if f]
        names = [f.split(".")[0].split("[")[0] for f in fields]
        if names and all(not str(row.get(n, "")).strip() for n in names):
            continue
        rendered = line.format_map(_Blank(row))
        rendered = re.sub(r"\(\s*\)", "", rendered)
        rendered = re.sub(r"\[\s*,?\s*\]", "", rendered)
        rendered = re.sub("(^\\s*\u2014\\s*)|(\\s*\u2014\\s*$)", "", rendered)  # \u2014: the em dash, escaped
        rendered = re.sub(r",\s*\]", "]", rendered)
        rendered = re.sub(r"\s{2,}", " ", rendered).strip()
        if rendered:
            lines.append(rendered)
    return "\n".join(lines)


def item_input_hash(text: str, image_sha256: str, label: str, chunker_version: str) -> str:
    h = hashlib.sha256()
    h.update(b"text:" + hashlib.sha256(text.encode()).digest())
    h.update(b"image:" + (image_sha256 or "none").encode())
    h.update(b"label:" + (label or "").encode())
    h.update(b"chunker:" + chunker_version.encode())
    return "sha256:" + h.hexdigest()


def profile_recipe(path: Path) -> tuple[str, str, str]:
    spec = tomllib.loads(path.read_text())
    return spec["source"]["text"]["template"], spec["source"]["image"]["label_template"], spec["corpus"]["chunker_version"]


def shards(pin: dict, cache: Path) -> list[Path]:
    from huggingface_hub import snapshot_download

    snapshot_download(
        pin["repo"], repo_type="dataset", revision=pin["revision"], allow_patterns=[pin["files"]], local_dir=cache
    )
    found = sorted(cache.glob(pin["files"]))
    if not found:
        env.die(f"no files matched {pin['files']} at {pin['revision']}")
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep-parquet", action="store_true", help="keep the downloaded shards under $MTG_DATA/.snapshot")
    args = ap.parse_args()
    import pyarrow.parquet as pq

    root = env.data_root()
    if root is None:
        env.die("MTG_DATA is not set; export MTG_DATA=/path/to/an/empty/dir")
    # refuse before the first write: an existing data root is never overwritten
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        env.die(f"MTG_DATA={root} is not empty; point it at an empty or new directory")
    root.mkdir(parents=True, exist_ok=True)
    pin = tomllib.loads(SOURCES.read_text())["snapshot"]
    template, label_tpl, chunker = profile_recipe(env.PROFILES / pin["profile"])
    images = root / "images" / "normal" / "front"
    images.mkdir(parents=True, exist_ok=True)
    db = root / "mtg.sqlite"
    con = sqlite3.connect(db)
    con.execute(f"CREATE TABLE cards ({', '.join(TEXT_FIELDS)}, image_uri)")
    con.execute("CREATE TABLE names_localized (oracle_id, printed_name, lang, lang_rank)")

    rows, keys_hash, tree = [], hashlib.sha256(), []
    cache = root / ".snapshot"
    for shard in shards(pin, cache):
        table = pq.read_table(shard)
        for r in table.to_pylist():
            data = r["image"]["bytes"]
            digest = hashlib.sha256(data).hexdigest()
            if digest != r["image_sha256"] or len(data) != r["image_bytes"]:
                env.die(f"scan of {r['key']} does not match its image_sha256 / image_bytes")
            img = r["img_id"]
            path = images / img[0] / img[1] / f"{img}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            uri = f"normal/front/{img[0]}/{img[1]}/{img}.jpg"
            con.execute("INSERT INTO cards VALUES (?,?,?,?,?,?,?,?)", (*[r[f] for f in TEXT_FIELDS], uri))
            if r["pt_name"] is not None:
                con.execute("INSERT INTO names_localized VALUES (?,?,?,?)", (r["oracle_id"], r["pt_name"], "pt", 1))
            rows.append(r | {"image": None})
            tree.append(f"{path.relative_to(root).as_posix()} {digest}")
        if not args.keep_parquet:
            shard.unlink()
    con.commit()
    con.close()

    rows.sort(key=lambda r: r["ordinal"])
    if [r["ordinal"] for r in rows] != list(range(len(rows))) or len(rows) != pin["rows"]:
        env.die(f"expected {pin['rows']} rows with ordinals 0..n-1, got {len(rows)}")
    if sorted(rows, key=lambda r: (r["img_id"], r["oracle_id"])) != rows:
        env.die("the snapshot's ordinal order is not the profiles' order_by (img_id, oracle_id)")
    corpus = hashlib.sha256()
    for r in rows:
        keys_hash.update(r["key"].encode() + b"\n")
        text = render_template(template, r)
        label = label_tpl.format_map(_Blank(r)).strip()
        corpus.update(item_input_hash(text, r["image_sha256"], label, chunker).encode())
    got = "sha256:" + corpus.hexdigest()
    images_tree = "sha256:" + hashlib.sha256("\n".join(sorted(tree)).encode()).hexdigest()
    result = {
        "snapshot": pin,
        "rows": len(rows),
        "keys_hash": "sha256:" + keys_hash.hexdigest(),
        "images_tree_hash": images_tree,
        "corpus_input_hash": got,
    }
    print(json.dumps({k: v for k, v in result.items() if k != "snapshot"}, indent=1))
    if got != pin["corpus_input_hash"]:
        env.die(f"corpus_input_hash {got} differs from the release's {pin['corpus_input_hash']}")
    if pin.get("keys_hash") and result["keys_hash"] != pin["keys_hash"]:
        env.die(f"keys_hash {result['keys_hash']} differs from the pin {pin['keys_hash']}")
    if pin.get("images_tree_hash") and images_tree != pin["images_tree_hash"]:
        env.die(f"images_tree_hash {images_tree} differs from the pin {pin['images_tree_hash']}")
    # written last: prepared.json exists only for a data root that passed every check
    (root / "prepared.json").write_text(json.dumps(result | {"matches_release": True}, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
