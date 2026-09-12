"""Section 48 capstone starters. Fixture model only. No live key."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

STARTERS = {
    "dataflow": ROOT / "labs" / "19_dataflow" / "starter",
    "research": ROOT / "labs" / "19_research" / "starter",
    "talentflow": ROOT / "labs" / "19_talentflow" / "starter",
}
SOLUTIONS = {
    "dataflow": ROOT / "labs" / "19_dataflow" / "solution",
    "research": ROOT / "labs" / "19_research" / "solution",
    "talentflow": ROOT / "labs" / "19_talentflow" / "solution",
}

FOUR_FILES = ("readme", "smoke", "golden", "fastapi")
TEMPLATE_ROWS = (
    "README",
    "Smoke",
    "Golden set",
    "The refuse line",
    "The honest when-not",
)


def count_todo(folder: Path) -> int:
    n = 0
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".md"}:
            continue
        if "__pycache__" in path.parts:
            continue
        n += path.read_text(encoding="utf-8").count("TODO")
    return n


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_each_starter_imports_and_has_todos(capsys):
    dataflow = load_module(
        STARTERS["dataflow"] / "graph.py", "capstone_dataflow_starter_graph"
    )
    research = load_module(
        STARTERS["research"] / "agent.py", "capstone_research_starter_agent"
    )
    talent = load_module(
        STARTERS["talentflow"] / "graph.py", "capstone_talentflow_starter_graph"
    )
    with pytest.raises(NotImplementedError):
        dataflow.classify({"ticket": "Where is order DF-1001?"})
    with pytest.raises(NotImplementedError):
        research.plan("returns")
    with pytest.raises(NotImplementedError):
        talent.load_resumes()
    counts = {name: count_todo(path) for name, path in STARTERS.items()}
    print("todo_count_dataflow", counts["dataflow"])
    print("todo_count_research", counts["research"])
    print("todo_count_talentflow", counts["talentflow"])
    for name, n in counts.items():
        assert n > 0, name
    captured = capsys.readouterr()
    print(captured.out, end="")


def test_each_solution_passes_in_temp_copy(tmp_path):
    env = os.environ.copy()
    env["DATAFLOW_UI_MODEL"] = "fixture"
    env["DATAFLOW_REFUNDS_PATH"] = str(tmp_path / "refunds.jsonl")
    env["PYTHONPATH"] = str(ROOT)
    for name, src in SOLUTIONS.items():
        dest = tmp_path / ("sol_" + name)
        shutil.copytree(
            src,
            dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        proc = subprocess.run(
            [PY, "-m", "pytest", "-q", str(dest / "check")],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.returncode == 0, name + "\n" + (proc.stdout or "") + (proc.stderr or "")


def test_review_template_has_five_rows():
    text = (ROOT / "labs" / "19_review" / "review_template.md").read_text(
        encoding="utf-8"
    )
    for row in TEMPLATE_ROWS:
        assert row in text, row
    lower = text.lower()
    assert "looks good" in lower
    assert "clone" in lower
    assert "one pass" in lower
    assert "one miss" in lower


def test_readme_is_under_sixty_lines_and_names_the_four_files():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) < 60, len(lines)
    lower = text.lower()
    for word in FOUR_FILES:
        assert word in lower, word
    assert "refuses when the knowledge base has nothing" in lower
