"""Integration test: bench_full_corpus.py end to end on a published release, offline.

  MTG_EVAL_RELEASE=<dir of release/v0.3/stills-5models> URNA_REPO=<urna checkout> \\
      python -m unittest benchmark/tests/test_eval_integration.py

It loads the siglip2 weights through the registry adapter, checks the model and
the items against the file, embeds 20 text queries and searches the stored image
space. The hub runs offline (HF_HUB_OFFLINE=1, no URNA_ALLOW_DOWNLOAD): the
pinned snapshot (timm/ViT-B-16-SigLIP2 at the revision the urna preset names)
must already be in the local cache, and a run that needs the network fails here
instead of fetching. URNA_REPO needs the urna loader that reads weights and
tokenizer from that snapshot; by name the siglip2 tokenizer fails offline.

The 20-query hit@k proves the path works; it is not a measurement, and
experiment 20 keeps the full-corpus numbers. The recorded run, made with the
network blocked, is benchmark/tests/data/eval-siglip2-stills-5models-q20.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
RELEASE = os.environ.get("MTG_EVAL_RELEASE")


def recorded(release: Path) -> dict:
    sums = dict(reversed(line.split(maxsplit=1)) for line in (release / "SHA256SUMS").read_text().splitlines())
    key = dict(line.split(" = ", 1) for line in (release / "CITATION_KEY").read_text().splitlines() if " = " in line)
    manifest = json.loads((release / "manifest.json").read_text())
    return {
        "file_hash": "sha256:" + sums["mtgdataset.urna"],
        "content_hash": key["content_hash"],
        "model_hash": manifest["models"]["siglip2"]["model_hash"],
    }


@unittest.skipUnless(RELEASE and os.environ.get("URNA_REPO"), "MTG_EVAL_RELEASE or URNA_REPO not set")
class SiglipOnStills5Models(unittest.TestCase):
    def test_twenty_queries_offline(self):
        release = Path(RELEASE)
        out = Path(tempfile.mkdtemp()) / "eval.json"
        run_env = {k: v for k, v in os.environ.items() if k != "URNA_ALLOW_DOWNLOAD"}
        run_env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        cmd = [
            sys.executable,
            str(TOOLS / "bench_full_corpus.py"),
            str(release / "mtgdataset.urna"),
            "--preset",
            "siglip2",
            "--queries",
            "20",
            "--seed",
            "7",
            "--out",
            str(out),
        ]
        proc = subprocess.run(cmd, env=run_env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        report = json.loads(out.read_text())
        for field, want in recorded(release).items():
            self.assertEqual(report[field], want, field)
        self.assertEqual(report["queries"], 20)
        hit = report["spaces"]["siglip2"]["hit"]
        values = [hit[k]["value"] for k in ("@1", "@5", "@10")]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in values))


if __name__ == "__main__":
    unittest.main()
