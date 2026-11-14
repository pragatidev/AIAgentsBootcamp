"""Lab 06.10.02 by code (18.2), fork_and_answer and edit_as typed by the student. The fixture model routes T-3001 to
refund in place of the real one, here and only here; the refund ledger is the lab's own temp file (setting
DATAFLOW_REFUNDS_PATH here first makes monkeypatch put it back). No server is started."""

import runpy

import pytest

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_10_02_fork_before_refund.py"
FORK = 'forked = fork_and_answer(desk, thread, "refund", APPROVE)\n'
REJECT = 'forked = fork_and_answer(desk, thread, "refund", {"action": "reject", "actor": "lab-reviewer"})\n'
QUESTION = "Approve this refund of 49.0 on order DF-1001?"
REPLY = "Refund issued for order DF-1001. Amount: 49.0."
ROW = "  row {'refunded': True, 'order_id': 'DF-1001', 'amount': 49.0, 'reason': 'reviewer approved'}"


@pytest.fixture
def scripted(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_chat_model", lambda **kwargs: FakeChatModel(route="refund"))
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "unused.jsonl"))


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, [line for line in capsys.readouterr().out.splitlines() if not line.startswith("actor=")]


def test_approved_fork_writes_a_second_row(scripted, capsys):
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    start = out.index("ticket T-3001 route refund parked True")
    assert out[start + 1 : start + 15] == [
        f"question {QUESTION} refunds_rows 0",
        f"approved {REPLY} refunds_rows 1",
        "  step 2 next ()",
        "  step 1 next ('refund',)",
        "  step 0 next ('classify',)",
        "  step -1 next ('__start__',)",
        "fork_point next ('refund',)",
        f"fork parked {QUESTION}",
        f"fork reply {REPLY} refunds_rows 2",
        ROW,
        ROW,
        "after_edit next ('lookup',)",
        "edited reply looked up DF-1001. Order DF-1001 is delivered. Item: desk lamp. parked False",
        "refunds_rows 2",
    ]


def test_typed_functions_on_a_lookup_ticket(scripted, capsys):
    lab, _ = _run(LAB, capsys)
    desk = build_v4_hitl(model=FakeChatModel(route="lookup"))
    thread = {"configurable": {"thread_id": "t"}}
    desk.invoke({"ticket": "Where is order DF-1001?"}, thread)
    forked = lab["fork_and_answer"](desk, thread, "lookup", {"action": "approve"})
    assert forked["reply"].startswith("looked up DF-1001.") and not forked.get("__interrupt__")
    edited = lab["edit_as"](desk, thread, "lookup", "classify", {"route": "policy"})
    assert "policy" in edited and not edited.get("__interrupt__")
    out = capsys.readouterr().out
    assert "fork parked" not in out and "after_edit next ('policy',)" in out


def test_break_rejected_fork_writes_no_row(scripted, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, FORK, REJECT)
    _, out = _run(broken, capsys)
    assert f"fork parked {QUESTION}" in out
    assert "fork reply Refund declined for order DF-1001. Reason: reviewer rejected the refund refunds_rows 1" in out
    assert out[-1] == "refunds_rows 1"
