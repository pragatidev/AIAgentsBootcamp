"""A copy of a lab with one edit, the way a student breaks it, laid out so the copy finds the repo's data files."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def lab_copy(lab: Path, tmp_path: Path, old: str, new: str) -> Path:
    """Write lab with old replaced by new (exactly one match) under tmp_path/labs, with techcorp/data beside it."""
    text = lab.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} appears {text.count(old)} times in {lab.name}"
    copy = tmp_path / "labs" / lab.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(text.replace(old, new), encoding="utf-8")
    data = tmp_path / "techcorp" / "data"
    if not data.exists():
        shutil.copytree(ROOT / "techcorp" / "data", data, ignore=shutil.ignore_patterns("audit.jsonl", "run_audit.jsonl"))
    return copy
