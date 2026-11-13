"""Lab 06.07.06 (16.6), build_desk typed by the student with the billing room as one node; the break compiles the
room with checkpointer=False. The fixture model routes to billing and finds a duplicate charge only when the ticket
says twice, so T-3012 explains the invoice and T-3005 parks."""

import runpy
from pathlib import Path

import pytest
from langgraph.types import Command

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.billing_subgraph import build_desk_with_billing
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_07_06_billing_subgraph.py"
CHOICE = "SUBGRAPH_CHECKPOINTER = None\n"
REPLY = "The invoice for DF-1023 is missing a tax line. No adjustment is due."
QUESTION = "Approve this adjustment of 22.0 on order DF-1010?"
BILLED_TWICE = "You billed me twice for order DF-1010. Please reverse the extra charge."


def _finding(messages) -> dict:
    text = str(messages[-1]["content"])
    return {"duplicate_charge": "twice" in text, "missing_tax_line": "tax line" in text, "disputed_fee": False}


@pytest.fixture
def fixture_model(monkeypatch):
    model = FakeChatModel(route="billing", reply=REPLY, structured={"BillingFinding": _finding})
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    return model


def _edges(graph):
    return {(e.source, e.target, e.conditional) for e in graph.get_graph().edges}


def _after(out: list[str], marker: str, n: int) -> list[str]:
    return out[out.index(marker) + 1 : out.index(marker) + 1 + n]


def test_lab_parks_inside_the_room_and_resumes(fixture_model, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "model FakeChatModel None"
    assert out[1] == "langchain-core 1.6.2" and out[2] == "langgraph 1.2.11"
    assert "room_alone_keys ['adjustment', 'invoice', 'reply', 'ticket']" in out
    assert "desk_keys ['reply', 'route', 'ticket']" in out
    assert f"desk route billing reply {REPLY}" in out
    assert _after(out, "first call, T-3005", 3) == ["   desk classify", "   billing fetch_invoice", "   billing decide_adjustment"]
    assert f"desk next ('billing',) question {QUESTION}" in out
    assert "inner_state ['adjustment', 'invoice', 'ticket'] inner next ('approve_adjustment',)" in out
    assert _after(out, "resume with approve", 2) == ["   billing approve_adjustment", "   desk billing"]
    assert "desk next () reply Adjustment of 22.0 approved on DF-1010" in out
    assert "\tsubgraph billing" in out


def test_typed_desk_matches_the_package(fixture_model):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    mine, package = lab["build_desk"](), build_desk_with_billing(model=fixture_model)
    assert set(mine.get_graph(xray=True).nodes) == set(package.get_graph(xray=True).nodes)
    assert _edges(mine) == _edges(package)
    for name, graph, extra in (("mine", mine, {"context": DeskContext(model=fixture_model)}), ("package", package, {})):
        thread = {"configurable": {"thread_id": f"test-16-6-{name}"}}
        parked = graph.invoke({"ticket": BILLED_TWICE}, thread, **extra)
        assert parked["__interrupt__"][0].value["question"] == QUESTION
        assert graph.invoke(Command(resume="approve"), thread, **extra)["reply"] == "Adjustment of 22.0 approved on DF-1010"


def test_break_checkpointer_false_reruns_the_room(fixture_model, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, CHOICE, "SUBGRAPH_CHECKPOINTER = False\n")
    runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert f"desk next ('billing',) question {QUESTION}" in out
    assert "inner_state None inner next None" in out
    assert _after(out, "resume with approve", 4) == [
        "   billing fetch_invoice",
        "   billing decide_adjustment",
        "   billing approve_adjustment",
        "   desk billing",
    ]
    assert "desk next () reply Adjustment of 22.0 approved on DF-1010" in out
