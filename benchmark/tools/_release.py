"""Read a build's manifest in either layout, and check a model against the file before using it.

Two layouts carry the same manifest:
  candidate   <name>.urna beside <name>.manifest.json, with the `items` list embedded
  release     <name>.urna beside manifest.json, with `items` stripped to items.jsonl.gz
              ({"stripped_to": "items.jsonl.gz", "n": ..., "fields": [...]})

No urna import here: the tools that need a checkout import this, and so can the tests.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import _bench_env as env


def load_build_manifest(index: Path) -> dict:
    """The manifest of the build `index` belongs to, with `items` always a full list."""
    candidates = [index.with_name(index.stem + ".manifest.json"), index.with_name("manifest.json")]
    found = next((p for p in candidates if p.is_file()), None)
    if found is None:
        env.die(f"no manifest beside {index}: looked for {', '.join(p.name for p in candidates)}")
    manifest = json.loads(found.read_text())
    items = manifest.get("items")
    if isinstance(items, dict) and items.get("stripped_to"):
        path = index.with_name(items["stripped_to"])
        if not path.is_file():
            env.die(f"{found.name} strips its items to {path.name}, which is not beside {index.name}")
        with gzip.open(path, "rt") as f:
            manifest["items"] = [json.loads(line) for line in f if line.strip()]
        if len(manifest["items"]) != items.get("n"):
            env.die(f"{path.name} has {len(manifest['items'])} items, {found.name} says {items.get('n')}")
    elif not isinstance(items, list):
        env.die(f"{found.name} has no items list")
    return manifest


def check_model_identity(
    preset: str, adapter_hash: str, adapter_dim: int, manifest: dict, file_spaces: list[dict], spaces: list[dict]
) -> None:
    """Refuse a model that is not the one the file was built with.

    The adapter's model_hash (a fingerprint over the snapshot's files, so it also
    pins the revision) must equal the manifest's record for the preset and the
    model_hash stored in every space of the file the evaluation will search; a
    space's dim must fit the model (equal, or a prefix slice of it).
    """
    want = manifest.get("models", {}).get(preset, {}).get("model_hash")
    if not want:
        env.die(f"the manifest records no model_hash for {preset}")
    if adapter_hash != want:
        env.die(f"the local {preset} snapshot has model_hash {adapter_hash}, the file was built with {want}")
    stored = {s.get("name"): s for s in file_spaces}
    for space in spaces:
        fs = stored.get(space["name"])
        if fs is None:
            env.die(f"space {space['name']} is in the manifest but not in the file")
        for field in ("model_hash", "dim"):
            if not fs.get(field):
                env.die(f"space {space['name']} in the file records no {field}; the model cannot be checked")
        if fs["model_hash"] != want:
            env.die(f"space {space['name']} stores model_hash {fs['model_hash']}, the manifest says {want}")
        dim = space.get("dim") or adapter_dim
        if dim > adapter_dim:
            env.die(f"space {space['name']} has dim {dim}, more than the model's {adapter_dim}")
        if fs["dim"] != dim:
            env.die(f"space {space['name']} stores dim {fs['dim']}, the manifest implies {dim}")


def check_items(items: list[dict], n_chunks: int, chunk_ids: list[str]) -> None:
    """The manifest's items must be the file's chunks: one item per chunk, ordinals 0..n-1."""
    if len(items) != n_chunks or len(chunk_ids) != n_chunks:
        env.die(f"the manifest lists {len(items)} items, the file holds {n_chunks} chunks ({len(chunk_ids)} ids)")
    ordinals = [it.get("ordinal") for it in items]
    if sorted(ordinals) != list(range(n_chunks)):
        env.die("the manifest's item ordinals are not 0..n-1, one per chunk")
    keys = [it.get("key") for it in items]
    if None in keys or len(set(keys)) != len(keys):
        env.die("the manifest's item keys are missing or repeated")
