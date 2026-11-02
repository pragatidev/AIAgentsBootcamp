"""Lab 08.04.06 (25.6), answer_question typed by the student. A scripted model and fixed passages stand in for the
real ones here, and only here. The lab's own pytest run stays under its __main__ guard."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs import rag_graph as G
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "08_04_06_portfolio_knowledge_desk.py"
PROCEDURES = "dataflow/knowledge_base/internal_operations/support_operations/customer_support_procedures.markdown"
REFUND = {"text": "Agent (Level 1): Approve refunds under 30 days.", "source": PROCEDURES, "folder": "internal_operations", "heading_path": "6. Refund and Cancellation Procedures > 6.1 Authorization Levels"}
STRANGER = {"text": "Standard shipping is five business days.", "source": "dataflow/wiki/shipping.md", "folder": "wiki", "heading_path": "DataFlow shipping"}


def _route(messages):
    return {"route": "lookup" if "DF-" in str(messages[-1]["content"]) else "retrieve"}


def _grade(messages):
    return {"label": "keep" if "Approve refunds" in str(messages[-1]["content"]) else "drop", "reason": "fixture"}


def _model():
    return FakeChatModel(reply="An agent can approve refunds under 30 days.", structured={"Route": _route, "Grade": _grade})


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: _model())
    monkeypatch.setattr(G, "get_index", lambda *a, **k: object())
    monkeypatch.setattr(G, "search", lambda index, q, k=3, folder=None: [dict(REFUND)] if "approve a refund" in q.lower() else [dict(STRANGER)])


@pytest.mark.parametrize("which", ["lab", "package"])
def test_three_tickets(which):
    fn = runpy.run_path(str(LAB), run_name="lab_08_04_06")["answer_question"] if which == "lab" else G.answer_question
    graph = G.build_rag_graph(model=_model(), scope="all")
    policy = fn(graph, "Who can approve a refund under 30 days?")
    assert policy["refused"] is False and policy["sources"] == [PROCEDURES] and "6.1 Authorization Levels" in policy["reply"]
    unknown = fn(graph, "Do you sell coffee beans in the DataFlow shop?")
    assert unknown["refused"] is True and unknown["sources"] == [] and unknown["retrieved"] is True
    order = fn(graph, "Where is order DF-1002?")
    assert order["route"] == "lookup" and order["refused"] is False and order["retrieved"] is False and "DF-1002" in order["reply"]


def test_the_run_prints_the_checks(capsys):
    runpy.run_path(str(LAB), run_name="lab_08_04_06")
    out = capsys.readouterr().out.splitlines()
    for line in ("desk support_agent scope all", "policy_cites_procedures True", "unknown_refused True", "order_route lookup", "order_retrieved False", "order_refused False"):
        assert line in out
    assert not any(line.startswith("pytest_exit") for line in out)


def test_the_break_calls_a_lookup_a_refusal(tmp_path, capsys):
    broken = lab_copy(LAB, tmp_path, '        "refused": reply.startswith(REFUSE_TEMPLATE.split(".")[0]),\n', '        "refused": not sources,\n')
    runpy.run_path(str(broken), run_name="lab_08_04_06")
    assert "order_refused True" in capsys.readouterr().out.splitlines()
