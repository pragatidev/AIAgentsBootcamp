"""The 2025 vendor tour does not leak into the package the student runs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_initialize_agent_absent_from_package():
    hits = []
    roots = [ROOT / "northstar", ROOT / "labs", ROOT / "config.py"]
    for root in roots:
        paths = [root] if root.is_file() else list(root.rglob("*.py"))
        for path in paths:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "initialize_agent" in text:
                hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_archive_is_not_on_the_learner_path():
    assert (ROOT / "_archive" / "2025_live").is_dir()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "_archive/2025_live" in readme
    assert "not the path" in readme.lower() or "not the learner" in readme.lower()
