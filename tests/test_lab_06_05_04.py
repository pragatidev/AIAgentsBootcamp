"""Lab 06.05.04 (14.4), edit_in_the_answer, edit_the_state and who_changed_it typed by the student. A fixture model stands
in for the real one here, and only here; the refund ledger is a temp file through DATAFLOW_REFUNDS_PATH."""

import runpy

import pytest

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools.refund import read_refunds
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_05_04_edit_state_before_resume.py"
REPO_LEDGER = ROOT / "dataflow" / "data" / "refunds.jsonl"
EDIT = '    graph.update_state(config, {"refund_amount": amount})\n'
RESUME = '    out = resume_with(graph, config, "approve")\n'


@pytest.fixture
def refund_desk(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="refund"))
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "ledger" / "refunds.jsonl"))


def _ledger_state():
    return REPO_LEDGER.read_bytes() if REPO_LEDGER.exists() else None


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    out = [line for line in capsys.readouterr().out.splitlines() if not line.startswith("actor=")]
    return lab, out


def test_lab_both_ways_pay_twenty_and_one_names_who(refund_desk, capsys):
    before = _ledger_state()
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    start = out.index("parked lab-14-4-answer amount 49.0 from order")
    assert out[start:] == [
        "parked lab-14-4-answer amount 49.0 from order",
        "parked lab-14-4-state amount 49.0 from order",
        "reply Refund issued for order DF-1001. Amount: 20.0.",
        "state_after lab-14-4-state next () refund_amount 20.0",
        "reply Refund issued for order DF-1001. Amount: 20.0.",
        "refund_row {'refunded': True, 'order_id': 'DF-1001', 'amount': 20.0, 'reason': 'reviewer approved'}",
        "refund_row {'refunded': True, 'order_id': 'DF-1001', 'amount': 20.0, 'reason': 'reviewer approved'}",
        "record lab-14-4-answer decision {'decision': 'approve', 'amount': 20.0, 'actor': 'maria'} actor maria",
        "checkpoints lab-14-4-answer ['input', 'loop', 'loop', 'loop']",
        "record lab-14-4-state decision approve actor None",
        "checkpoints lab-14-4-state ['input', 'loop', 'loop', 'update', 'loop']",
    ]
    assert _ledger_state() == before


def test_typed_ways_on_a_fresh_desk(refund_desk, capsys):
    lab, _ = _run(LAB, capsys)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    for thread_id in ("a", "b"):
        graph.invoke({"ticket": "Please refund order DF-1001."}, {"configurable": {"thread_id": thread_id}})
    assert lab["edit_in_the_answer"](graph, "a", 12.5, "sam")["reply"].endswith("Amount: 12.5.")
    assert lab["edit_the_state"](graph, "b", 7.0)["reply"].endswith("Amount: 7.0.")
    assert [row["amount"] for row in read_refunds()][-2:] == [12.5, 7.0]


def test_break_edit_after_the_write_pays_the_old_amount(refund_desk, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, EDIT + RESUME, RESUME + EDIT)
    _, out = _run(broken, capsys)
    start = out.index("state_after lab-14-4-state next () refund_amount 20.0")
    assert out[start + 1 : start + 4] == [
        "reply Refund issued for order DF-1001. Amount: 49.0.",
        "refund_row {'refunded': True, 'order_id': 'DF-1001', 'amount': 20.0, 'reason': 'reviewer approved'}",
        "refund_row {'refunded': True, 'order_id': 'DF-1001', 'amount': 49.0, 'reason': 'reviewer approved'}",
    ]
    assert out[-1] == "checkpoints lab-14-4-state ['input', 'loop', 'loop', 'loop', 'update']"
