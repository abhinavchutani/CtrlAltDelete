"""v1 freeze guard: sha256 of every out/*_submission.csv (docs/V2_ARCHITECTURE.md, "How Track A stays fixed").

    python -m src.v1_manifest           # (re)write out/v1_manifest.json; only a human-approved v1 fix does this
tests/test_v2_guard.py checks the CSVs against it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.db import REPO_ROOT

MANIFEST = REPO_ROOT / "out" / "v1_manifest.json"


def digests(out: Path = REPO_ROOT / "out") -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob("*_submission.csv"))}


if __name__ == "__main__":
    MANIFEST.write_text(json.dumps(digests(), indent=1) + "\n")
    print(f"{MANIFEST}: {len(digests())} files")
