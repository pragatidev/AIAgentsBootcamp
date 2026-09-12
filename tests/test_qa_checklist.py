"""10.3 QA checklist. Every row has a path. Bugs name a collectable test."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / "eval" / "qa" / "checklist.md"
BUGS = ROOT / "eval" / "qa" / "bugs.md"


def _table_rows(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0].lower() == "check" or set(cells[0]) <= {"-", ":"}:
            continue
        path = cells[1] if len(cells) > 1 else ""
        status = cells[2] if len(cells) > 2 else ""
        rows.append((cells[0], path, status))
    return rows


def test_every_checklist_row_has_a_path_that_exists():
    text = CHECKLIST.read_text(encoding="utf-8")
    rows = _table_rows(text)
    assert rows, "checklist has no rows"
    names = [row[0] for row in rows]
    assert "parked write" in names
    for check, path, _status in rows:
        assert path, "empty path for " + check
        target = ROOT / path
        assert target.is_file(), check + " path missing: " + path


def test_bugs_md_names_a_test_pytest_can_collect():
    text = BUGS.read_text(encoding="utf-8")
    node = "eval/ui/test_dataflow_chat.py::test_parked_refund_shows_parked"
    assert node in text
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            node,
            "--override-ini",
            "addopts=",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "test_parked_refund_shows_parked" in result.stdout
