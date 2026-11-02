"""Lab 08.04.04 (25.4), should_refuse typed by the student. A scripted model and fixed passages stand in for the
real ones here, and only here."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs import crag
from dataflow.graphs import rag_graph as G
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "08_04_04_refuse_on_empty.py"
PASSAGES = [
    {"text": "Returns are allowed within 30 days of delivery.", "source": "dataflow/wiki/return_policy.md", "folder": "wiki", "score": 1.0},
    {"text": "Standard shipping is five business days.", "source": "dataflow/wiki/shipping.md", "folder": "wiki", "score": 1.1},
    {"text": "Passwords must be at least twelve characters.", "source": "dataflow/wiki/security.md", "folder": "wiki", "score": 1.2},
]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    model = FakeChatModel(route="retrieve", reply=["Does the DataFlow shop sell coffee beans?", "We do not list coffee beans."], structured={"Grade": {"label": "drop", "reason": "not covered"}})
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    monkeypatch.setattr(G, "retrieve_passages", lambda *a, **k: [dict(p) for p in PASSAGES])


def _out(path, capsys):
    runpy.run_path(str(path), run_name="__main__")
    return capsys.readouterr().out.splitlines()


def test_the_rows_and_the_refusal(capsys):
    out = _out(LAB, capsys)
    assert [line.rsplit("-> ", 1)[1] for line in out if line.startswith("should_refuse ")] == ["False", "False", "True", "True", "False"]
    assert out.count("retrieved 3 kept 0") == 2
    assert "edge_taken refuse" in out and "REFUSE True" in out and "cites_rejected False" in out
    assert not any(line.startswith("Sources:") for line in out)


def test_typed_check_matches_the_module():
    lab = runpy.run_path(str(LAB), run_name="__main__")
    for state in lab["ROWS"]:
        assert lab["should_refuse"](state) is crag.should_refuse(state)


def test_the_break_answers_from_rejected_passages(tmp_path, capsys):
    old = '''    kept = [row for row in state.get("grades") or [] if row.get("label") == "keep"]
    if kept or state.get("graded"):
        return False
    return int(state.get("rewrites") or 0) >= int(max_rewrites)
'''
    new = '''    return not state.get("passages") and int(state.get("rewrites") or 0) >= int(max_rewrites)
'''
    out = _out(lab_copy(LAB, tmp_path, old, new), capsys)
    assert [line.rsplit("-> ", 1)[1] for line in out if line.startswith("should_refuse ")][2] == "False"
    assert "edge_taken generate" in out
    assert "REFUSE False" in out and "cites_rejected True" in out


def _record_generate(monkeypatch):
    seen = []
    real = G.generate

    def recording(state, runtime=None, **kwargs):
        seen.append({"read": list(state.get("graded") or state.get("passages") or []), **kwargs})
        return real(state, runtime, **kwargs)

    monkeypatch.setattr(G, "generate", recording)
    return seen


def test_refuse_on_refuses(monkeypatch, capsys):
    seen = _record_generate(monkeypatch)
    out = _out(LAB, capsys)
    assert "refuse_check on" in out and "edge_taken refuse" in out and "REFUSE True" in out
    assert seen == []


def test_refuse_off_generates_on_what_the_grade_kept(monkeypatch, tmp_path, capsys):
    seen = _record_generate(monkeypatch)
    out = _out(lab_copy(LAB, tmp_path, "REFUSE_CHECK_ON = True\n", "REFUSE_CHECK_ON = False\n"), capsys)
    assert "refuse_check off" in out
    assert out.count("retrieved 3 kept 0") == 2 and "rewritten 'Does the DataFlow shop sell coffee beans?'" in out
    assert "edge_taken generate" in out and "edge_taken refuse" not in out
    assert "generate_read 0 passages" in out and "We do not list coffee beans." in out
    assert "REFUSE False" in out and "cites_rejected False" in out
    assert "Sources: none (this reply did not use the knowledge base)" in out
    assert len(seen) == 1 and seen[0]["read"] == []
    assert not seen[0]["allow_ungrounded"] and seen[0]["system_prompt"] is None
