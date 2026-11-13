"""Lab 06.06.06 (15.4), show and full_run typed by the student. A fixture model stands in for the real one here, and
only here (lookup for the first ticket, refund for the second); the ledger is a temp file; the lab's last call to
pytest is recorded, not started, so the suite does not run inside itself."""

import runpy
import subprocess
from types import SimpleNamespace

import pytest

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_06_06_full_run.py"
RESUME = '    print("reply", show(graph.stream(Command(resume="approve"), refund_thread, **STREAM)))\n'
REPLY = "Refund issued for order DF-1001. Amount: 49.0."


def _desk_model(**kwargs):
    return FakeChatModel(structured={"HitlDecision": [{"route": "lookup"}, {"route": "refund"}]})


@pytest.fixture
def desk(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_chat_model", _desk_model)
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "ledger" / "refunds.jsonl"))
    calls = []

    def record(argv, **kwargs):
        calls.append((argv, kwargs.get("cwd")))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", record)
    return calls


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_three_runs_through_one_printer(desk, capsys):
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    start = out.index("run lookup")
    assert out[start:] == [
        "run lookup",
        "node classify wrote ['route']",
        "node lookup wrote ['order', 'reply']",
        "message_chunks 0",
        "reply looked up DF-1002. Order DF-1002 is in_transit. Item: USB-C hub.",
        "run refund",
        "node classify wrote ['route']",
        "parked Approve this refund of 49.0 on order DF-1001?",
        "message_chunks 0",
        "reply None",
        "rows_before_resume 0",
        "run approve",
        out[start + 12],
        "node refund wrote ['decision', 'order', 'refund', 'reply']",
        "message_chunks 0",
        f"reply {REPLY}",
        "refunds_rows 1",
        "thread_next ()",
        "pytest_exit 0",
    ]
    assert out[start + 12].startswith("actor=anon step=issue_refund run=")  # dataflow/ops/tracer.py, at the write
    (argv, cwd), = desk
    assert argv[1:] == ["-m", "pytest", "tests/test_dataflow_stream.py", "-q"] and cwd == ROOT


def test_show_reads_a_parked_stream(desk, capsys):
    lab, _ = _run(LAB, capsys)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    stream = graph.stream({"ticket": "Refund order DF-1001 please"}, {"configurable": {"thread_id": "t"}}, **lab["STREAM"])
    assert lab["show"](stream) is None
    out = capsys.readouterr().out.splitlines()
    assert out == ["node classify wrote ['route']", "parked Approve this refund of 49.0 on order DF-1001?", "message_chunks 0"]


def test_break_resume_without_the_thread(desk, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, RESUME, RESUME.replace("refund_thread, ", ""))
    with pytest.raises(ValueError, match="Checkpointer requires one or more of the following 'configurable' keys: thread_id"):
        runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[-2:] == ["rows_before_resume 0", "run approve"]
    assert not desk
