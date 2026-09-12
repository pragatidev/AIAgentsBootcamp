"""Repo root works from cwd, a lab folder, and the viralLoom nest."""

from pathlib import Path

from src.paths import find_repo_root


def test_root_from_package():
    root = find_repo_root()
    assert (root / "config.py").is_file()
    assert (root / "dataflow").is_dir()
    assert (root / "talentflow" / "data").is_dir()


def test_root_from_lab_hint():
    section = Path(__file__).resolve().parents[1] / "labs"
    root = find_repo_root(section)
    assert (root / "config.py").is_file()


def test_root_from_viralloom_nest():
    viralloom = Path(__file__).resolve().parents[6]
    if viralloom.name.lower() != "viralloom" and (viralloom / "data").is_dir() is False:
        return
    root = find_repo_root(viralloom)
    assert (root / "config.py").is_file()
