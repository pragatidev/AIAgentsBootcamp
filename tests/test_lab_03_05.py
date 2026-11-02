"""Lab 03.05, check_map typed by the student, against the shipped copy. No model."""

import runpy
from pathlib import Path

import pytest

from dataflow.context.map_text import check_map, load_map, map_lines

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_05_map_file.py"
MAP_FILE = Path(__file__).resolve().parents[1] / "dataflow" / "context" / "MAP.md"


@pytest.fixture(scope="module")
def lab():
    before = MAP_FILE.read_bytes()
    out = runpy.run_path(str(LAB), run_name="__main__")
    assert MAP_FILE.read_bytes() == before, "the lab must never write MAP.md"
    return out


@pytest.mark.parametrize("which", ["module", "lab"])
def test_check_map_both_copies(lab, which):
    check = check_map if which == "module" else lab["check_map"]
    shipped = load_map()
    assert check(shipped) == []
    assert check(shipped + "refund_policy.md | when the customer asks for a refund\n") == [
        "refund_policy.md: not readable"
    ]
    assert check(shipped + "shipping.md - when asked\n") == ["shipping.md - when asked: needs a name, a bar and a when"]
    assert check(shipped + "shipping.md | always\n") == ["shipping.md | always: needs a name, a bar and a when"]


def test_the_lab_prints_a_clean_map(capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert "map_problems []" in out
    assert "fat_chars 58816" in out
    assert "map_file dataflow/context/MAP.md" in out
    assert len([line for line in out if line.startswith("map_entry ")]) == len(map_lines()) == 12
