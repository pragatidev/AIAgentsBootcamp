"""Lab 06.05.03 (14.3), resume_with, park and answer typed by the student. A fixture model stands in for the real one
here, and only here; the refund ledger is a temp file through DATAFLOW_REFUNDS_PATH, as in the HITL tests."""

import runpy

import pytest

import config
from dataflow.graphs import v4_hitl
from dataflow.tools.refund import read_refunds
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_05_03_resume_approve_reject.py"
REPO_LEDGER = ROOT / "dataflow" / "data" / "refunds.jsonl"
ANSWER = 'answer(graph, "lab-14-3-approve", "approve")\n'
TYPO = 'answer(graph, "lab-14-3-aprove", "approve")\n'
QUESTION = "question Approve this refund of 49.0 on order DF-1001?"


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


def test_lab_approves_one_and_rejects_one(refund_desk, capsys):
    before = _ledger_state()
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    start = out.index("parked lab-14-3-approve next ('refund',)")
    assert out[start : start + 4] == [
        "parked lab-14-3-approve next ('refund',)",
        QUESTION,
        "parked lab-14-3-reject next ('refund',)",
        QUESTION,
    ]
    assert out[start + 4 : start + 9] == [
        "answer approve on lab-14-3-approve",
        "reply Refund issued for order DF-1001. Amount: 49.0.",
        "parked_again False",
        "rows_written 1",
        "thread_next ()",
    ]
    assert out[start + 9 : start + 14] == [
        "answer reject on lab-14-3-reject",
        "reply Refund declined for order DF-1001. Reason: reviewer rejected the refund",
        "parked_again False",
        "rows_written 0",
        "thread_next ()",
    ]
    assert out[-3:] == ["final lab-14-3-approve next ()", "final lab-14-3-reject next ()", "refunds_rows 1"]
    assert _ledger_state() == before


def test_typed_resume_with_is_the_package_call(refund_desk, capsys):
    lab, _ = _run(LAB, capsys)
    for resume in (lab["resume_with"], v4_hitl.resume_with):
        graph = v4_hitl.build_v4_hitl(model=FakeChatModel(route="refund"))
        assert lab["park"](graph, "Please refund order DF-1001.", "t") == ("refund",)
        out = resume(graph, {"configurable": {"thread_id": "t"}}, "approve")
        assert out["reply"] == "Refund issued for order DF-1001. Amount: 49.0."
    assert len(read_refunds()) == 1 + 2


def test_break_thread_typo_parks_a_new_thread_and_loses_the_approval(refund_desk, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, ANSWER, TYPO)
    _, out = _run(broken, capsys)
    start = out.index("answer approve on lab-14-3-aprove")
    assert out[start : start + 5] == [
        "answer approve on lab-14-3-aprove",
        "reply None",
        "parked_again True",
        "rows_written 0",
        "thread_next ('refund',)",
    ]
    assert out[-3:] == ["final lab-14-3-approve next ('refund',)", "final lab-14-3-reject next ()", "refunds_rows 0"]
