"""Lab 06.06.03 (15.3), drive typed by the student. A fixture model stands in for the real one here, and only here; the
refund ledger is a temp file through DATAFLOW_REFUNDS_PATH, as in the HITL tests."""

import runpy
from pathlib import Path

import pytest
from langgraph.types import Command

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_06_03_stream_events.py"
REPO_LEDGER = ROOT / "dataflow" / "data" / "refunds.jsonl"
PARKED = "    parked = stream.interrupted\n"
REPLY = "Refund issued for order DF-1001. Amount: 49.0."


@pytest.fixture
def refund_desk(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="refund"))
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "ledger" / "refunds.jsonl"))


def _ledger_state():
    return REPO_LEDGER.read_bytes() if REPO_LEDGER.exists() else None


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_lab_parks_then_resumes(refund_desk, capsys):
    before = _ledger_state()
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    first = out[out.index("value_step 0 keys ['ticket']") : out.index("reviewer answers approve")]
    assert first == [
        "value_step 0 keys ['ticket']",
        "value_step 1 keys ['route', 'ticket']",
        "value_step 2 keys ['route', 'ticket']",
        "output_keys ['route', 'ticket']",
        "interrupted True",
        "parked_on refund order DF-1001 amount 49.0",
        "question Approve this refund of 49.0 on order DF-1001?",
        "rows_after_first_stream 0",
    ]
    assert "output_keys ['decision', 'order', 'refund', 'reply', 'route', 'ticket']" in out
    assert out[-5:] == ["interrupted False", f"done route refund reply {REPLY}", "status done", "refunds_rows 1", "thread_next ()"]
    assert _ledger_state() == before


def test_typed_driver_on_a_fresh_desk(refund_desk, capsys):
    lab, _ = _run(LAB, capsys)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    thread = {"configurable": {"thread_id": "t"}}
    status, payload = lab["drive"](graph, {"ticket": "Refund order DF-1001 please"}, thread)
    assert (status, payload["order_id"], payload["amount"]) == ("parked", "DF-1001", 49.0)
    status, out = lab["drive"](graph, Command(resume="approve"), thread)
    assert (status, out["reply"]) == ("done", REPLY)
    lookup = build_v4_hitl(model=FakeChatModel(route="lookup"))
    status, out = lab["drive"](lookup, {"ticket": "Where is order DF-1002?"}, {"configurable": {"thread_id": "l"}})
    assert status == "done" and out["reply"].startswith("looked up DF-1002.")


def test_break_parked_false_says_done_with_no_reply(refund_desk, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, PARKED, "    parked = False\n")
    _, out = _run(broken, capsys)
    assert "interrupted False" in out and "interrupted True" not in out
    assert "output_keys ['route', 'ticket']" in out and "done route refund reply None" in out
    assert "reviewer answers approve" not in out
    assert out[-3:] == ["status done", "refunds_rows 0", "thread_next ('refund',)"]
