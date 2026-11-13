"""Lab 06.05.02 (14.2), refund_node typed by the student. A fixture model stands in for the real one here, and only here;
the refund ledger is a temp file through DATAFLOW_REFUNDS_PATH, as in the HITL tests."""

import runpy

import pytest
from langgraph.types import Command

import config
from dataflow.graphs import v4_hitl
from dataflow.tools.refund import read_refunds
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_05_02_park_the_refund.py"
REPO_LEDGER = ROOT / "dataflow" / "data" / "refunds.jsonl"
PAUSE = "    decision = interrupt(payload)\n"
EARLY_WRITE = (
    '    issue_refund.invoke({"order_id": order_id, "amount": amount, "reason": "written before anyone approved"})\n'
)
TICKET = "Hi, I want to return order DF-1001. The desk lamp is unused. Can I get a refund?"
REPLY = "Refund issued for order DF-1001. Amount: 49.0."


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


def test_lab_parks_then_approves(refund_desk, capsys):
    before = _ledger_state()
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    assert out[out.index("route refund") + 1] == "thread_next ('refund',)"
    assert "payload order_id DF-1001" in out and "payload amount 49.0" in out
    assert "payload amount_source order" in out
    assert "payload question Approve this refund of 49.0 on order DF-1001?" in out
    assert any(line.startswith("payload policy ") and "30 days" in line for line in out)
    assert "rows_while_parked 0" in out
    assert out[-4:-2] == [f"reply {REPLY}", "refund_row {'refunded': True, 'order_id': 'DF-1001', 'amount': 49.0, 'reason': 'reviewer approved'}"]
    assert out[-2:] == ["refunds_rows 1", "thread_next ()"]
    assert _ledger_state() == before


@pytest.mark.parametrize(
    "answer",
    ["approve", "reject", "banana", {"decision": "approve", "amount": 20.0}],
)
def test_typed_node_matches_the_package(refund_desk, capsys, answer):
    lab, _ = _run(LAB, capsys)
    seen = {}
    for name, node in (("typed", lab["refund_node"]), ("package", v4_hitl.refund_node)):
        graph = lab["build_desk"](node, FakeChatModel(route="refund"))
        thread = {"configurable": {"thread_id": name + str(answer)}}
        start = len(read_refunds())
        graph.invoke({"ticket": TICKET}, thread)
        payload = graph.get_state(thread).interrupts[0].value
        rows_parked = len(read_refunds()) - start
        done = graph.invoke(Command(resume=answer), thread)
        seen[name] = (payload, rows_parked, done["reply"], done["refund"], len(read_refunds()) - start)
    assert seen["typed"] == seen["package"]
    assert seen["typed"][1] == 0


def test_break_write_above_the_pause_runs_twice(refund_desk, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, PAUSE, EARLY_WRITE + PAUSE)
    _, out = _run(broken, capsys)
    assert "rows_while_parked 1" in out
    reasons = [line for line in out if line.startswith("refund_row ")]
    assert len(reasons) == 3
    assert sum("written before anyone approved" in line for line in reasons) == 2
    assert "reviewer approved" in reasons[-1]
    assert out[-2:] == ["refunds_rows 3", "thread_next ()"]
