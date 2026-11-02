"""Lab 08.03.05 (24.5), after_grade typed by the student. A scripted model and fixed passages stand in for the real
ones here, and only here."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs import crag
from dataflow.graphs import rag_graph as G
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "08_03_05_corrective_rag.py"
PASSAGES = [
    {"text": "Returns are allowed within 30 days of delivery when the item is unused.", "source": "dataflow/wiki/return_policy.md", "folder": "wiki", "score": 0.9},
    {"text": "Standard shipping is five business days.", "source": "dataflow/wiki/shipping.md", "folder": "wiki", "score": 1.1},
    {"text": "Passwords must be at least twelve characters.", "source": "dataflow/wiki/security.md", "folder": "wiki", "score": 1.2},
]
DROP, KEEP = {"label": "drop", "reason": "not this"}, {"label": "keep", "reason": "the return window"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    model = FakeChatModel(route="retrieve", reply=["What is the return process for an unused desk lamp?", "Yes, within 30 days.", "student discount Enterprise plan"], structured={"Grade": [DROP, DROP, DROP, KEEP, DROP, DROP, DROP]})
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    monkeypatch.setattr(G, "retrieve_passages", lambda *a, **k: [dict(p) for p in PASSAGES])


def _out(path, capsys):
    runpy.run_path(str(path), run_name="__main__")
    return capsys.readouterr().out.splitlines()


def test_the_rows_the_two_passes_and_the_refusal(capsys):
    out = _out(LAB, capsys)
    decisions = [line.rsplit("-> ", 1)[1] for line in out if line.startswith("after_grade ")]
    assert decisions == ["generate", "rewrite", "refuse", "widen", "generate", "refuse"]
    assert [line for line in out if line.startswith("grade_pass")][:2] == ["grade_pass kept 0 of 3", "grade_pass kept 1 of 3"]
    assert "rewrites 1" in out and "corrected True" in out
    assert "REFUSE True" in out


def test_typed_policy_matches_the_module():
    lab = runpy.run_path(str(LAB), run_name="__main__")
    for state, allowed in lab["ROWS"]:
        assert lab["after_grade"](dict(state), web_search_allowed=allowed) == crag.after_grade(dict(state), web_search_allowed=allowed)


def test_the_break_runs_away(tmp_path, capsys):
    line = '        return "generate"\n    if int(state.get("rewrites") or 0) < int(max_rewrites):\n'
    broken = lab_copy(LAB, tmp_path, line, '        return "generate"\n    if True:\n')
    out = _out(broken, capsys)
    decisions = [line.rsplit("-> ", 1)[1] for line in out if line.startswith("after_grade ")]
    assert decisions[2] == "rewrite"
    assert any(line.startswith("runaway GraphRecursionError Recursion limit of 12 reached") for line in out)
