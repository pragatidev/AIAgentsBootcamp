"""Repo root works from cwd, a lab folder, and the viralLoom nest."""

from pathlib import Path

from src.paths import NESTED_HINTS, find_repo_root


def test_root_from_package():
    root = find_repo_root()
    assert (root / "config.py").is_file()
    assert (root / "dataflow").is_dir()
    assert (root / "talentflow" / "data").is_dir()


def test_root_from_lab_hint():
    section = Path(__file__).resolve().parents[1] / "labs"
    root = find_repo_root(section)
    assert (root / "config.py").is_file()


def test_root_from_viralloom_nest(tmp_path, monkeypatch):
    # Build the nest in a temp folder so the test does not depend on where the clone sits.
    monkeypatch.delenv("BOOTCAMP_ROOT", raising=False)
    nest = tmp_path / NESTED_HINTS[0]
    (nest / "dataflow").mkdir(parents=True)
    (nest / "config.py").write_text("", encoding="utf-8")
    root = find_repo_root(tmp_path)
    assert root == nest.resolve()
