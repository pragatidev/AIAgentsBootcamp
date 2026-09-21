"""The 2025 vendor tour does not leak into the package the student runs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_initialize_agent_absent_from_package():
    hits = []
    roots = [
        ROOT / "dataflow",
        ROOT / "techcorp",
        ROOT / "talentflow",
        ROOT / "labs",
        ROOT / "config.py",
    ]
    for root in roots:
        paths = [root] if root.is_file() else list(root.rglob("*.py"))
        for path in paths:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "initialize_agent" in text:
                hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_2025_edition_lives_on_its_own_branch():
    # 2026-09-21: the 2025 notebooks left this branch; the README must tell a 2025 student where they went
    assert not (ROOT / "_archive" / "2025_live").exists()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "original-2025" in readme
    assert "git checkout original-2025" in readme


def test_northstar_is_off_the_learner_path():
    assert not (ROOT / "northstar").exists()
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "northstar" not in readme
