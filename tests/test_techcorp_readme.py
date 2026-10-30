"""The TechCorp README is a contract: a reviewer can follow it from clone to green tests on any machine. No model."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "techcorp" / "README.md"
CREATED_AT_RUN_TIME = {"techcorp/data/audit.jsonl", "techcorp/data/run_audit.jsonl"}


def _lines() -> list[str]:
    return README.read_text(encoding="utf-8").splitlines()


def test_readme_has_no_machine_paths():
    bad = [
        f"line {n}: {line}"
        for n, line in enumerate(_lines(), 1)
        if re.search(r"\b[A-Za-z]:[\\/]|/Users/|/home/|viralLoom", line)
    ]
    assert not bad, "a path from one machine: " + "; ".join(bad)


def test_every_file_the_readme_names_exists():
    named = set(re.findall(r"`((?:labs|tests|techcorp)/[^`\s]+\.(?:py|md|json|jsonl|txt))`", README.read_text(encoding="utf-8")))
    named |= set(re.findall(r"\b((?:labs|tests)/[\w./]+\.py)\b", README.read_text(encoding="utf-8")))
    missing = sorted(path for path in named - CREATED_AT_RUN_TIME if not (ROOT / path).is_file())
    assert named and not missing, missing


def test_readme_has_the_sections_a_reviewer_reads():
    headings = {line[3:].strip() for line in _lines() if line.startswith("## ")}
    for section in ("Run it", "Tests", "Design decisions", "Known limits", "Sample run"):
        assert section in headings, section


def test_every_test_the_readme_cites_exists():
    text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_*.py"))
    for name in re.findall(r"`(test_\w+)`", README.read_text(encoding="utf-8")):
        assert f"def {name}(" in text, name
