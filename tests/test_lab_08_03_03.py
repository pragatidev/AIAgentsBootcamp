"""Lab 08.03.03 (24.3), the grade node typed by the student. A scripted model and fixed passages stand in for the
real ones here, and only here."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs import rag_graph as G
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "08_03_03_agentic_rag_graph.py"
HANDBOOK = {"text": "Return equipment within 30 days of termination.", "source": "dataflow/knowledge_base/internal_operations/hr_policies/employee_handbook.txt", "folder": "internal_operations", "score": 0.81}
POLICY = {"text": "Returns are allowed within 30 days of delivery when the item is unused.", "source": "dataflow/wiki/return_policy.md", "folder": "wiki", "score": 0.84}


def _grade_by_source(messages):
    text = str(messages[-1]["content"])
    if "return_policy.md" in text:
        return {"label": "keep", "reason": "the customer return window"}
    return {"label": "wrong", "reason": "an employee rule, not a customer policy"}


def _model():
    return FakeChatModel(route="retrieve", reply="Yes, within 30 days of delivery.", structured={"Grade": _grade_by_source})


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: _model())
    monkeypatch.setattr(G, "retrieve_passages", lambda *a, **k: [dict(HANDBOOK), dict(POLICY)])
    monkeypatch.setattr(G, "search", lambda *a, **k: [dict(HANDBOOK), dict(POLICY)])
    monkeypatch.setattr(G, "get_index", lambda *a, **k: object())


def _out(path, capsys):
    runpy.run_path(str(path), run_name="__main__")
    return capsys.readouterr().out.splitlines()


def test_the_graph_is_printed_and_the_handbook_is_not_cited(capsys):
    out = _out(LAB, capsys)
    assert "nodes ['route', 'retrieve', 'grade', 'rewrite', 'generate', 'refuse', 'lookup', 'answer', 'widen', 'cite']" in out
    assert "edges" in " ".join(out) and any("retrieve -> grade" in line for line in out)
    assert out.count("handbook_retrieved True") == 2
    assert out.count("cited_handbook False") == 2
    assert "sources ['dataflow/wiki/return_policy.md']" in out


def test_typed_grade_matches_the_module():
    lab = runpy.run_path(str(LAB), run_name="lab_08_03_03")
    state = {"question": "Can I send back an unused lamp?", "passages": [dict(HANDBOOK), dict(POLICY)]}
    assert lab["grade"](state, model=_model()) == G.grade(state, model=_model())


def test_the_break_cites_the_handbook(tmp_path, capsys):
    broken = lab_copy(LAB, tmp_path, '        if label == "keep":\n', "        if label:\n")
    out = _out(broken, capsys)
    assert "cited_handbook True" in out
