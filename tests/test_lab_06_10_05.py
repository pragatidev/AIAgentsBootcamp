"""Lab 06.10.05 (18.5), run_traced and waterfall typed by the student. A fixture model stands in for the real one here,
and only here; the refund ledger is a temp file through DATAFLOW_REFUNDS_PATH and traces go to a temp folder through
the tracer's TRACES_DIR. The lab's last cell runs tests/test_dataflow_tracer.py with pytest; here that call is recorded,
not made (no pytest inside pytest), and the suite runs that file on its own."""

import json
import runpy
import subprocess

import pytest

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.ops import tracer as tracer_mod
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_10_05_wire_the_tracer.py"
REPO_LEDGER = ROOT / "dataflow" / "data" / "refunds.jsonl"
RESUME = "    final = graph.invoke(Command(resume=decision), run_config)\n"
UNTRACED = '    final = graph.invoke(Command(resume=decision), {"configurable": {"thread_id": thread_id}})\n'
REPLY = "Refund issued for order DF-1001. Amount: 49.0."


class _Done:
    returncode = 0


@pytest.fixture
def refund_desk(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="refund"))
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "ledger" / "refunds.jsonl"))
    monkeypatch.setattr(tracer_mod, "TRACES_DIR", tmp_path / "traces")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: calls.append(argv) or _Done())
    return calls


def _ledger_state():
    return REPO_LEDGER.read_bytes() if REPO_LEDGER.exists() else None


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_lab_traces_both_halves(refund_desk, capsys):
    before = _ledger_state()
    _, out = _run(LAB, capsys)
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    assert "parked True rows_while_parked 0" in out
    assert f"reply {REPLY}" in out and "refunds_rows 1" in out
    tree = out[out.index("waterfall") + 1 :]
    assert tree[0].startswith("run lab-18-5 ") and tree[0].endswith(" ok")
    assert sum(line.startswith("  chain LangGraph ") for line in tree) == 2
    assert any(line.startswith("    chain refund ") and line.endswith(" FAIL GraphInterrupt") for line in tree)
    assert any(line.startswith("    chain refund ") and line.endswith(" ok") for line in tree)
    assert "tools ['search_policy', 'search_policy', 'issue_refund']" in out
    assert "state_keys ['decision', 'order', 'refund', 'reply', 'route', 'ticket']" in out
    assert out[-1] == "pytest_exit 0"
    assert refund_desk[-1][-3:] == ["pytest", "tests/test_dataflow_tracer.py", "-q"]
    assert _ledger_state() == before


def test_typed_functions_on_a_fresh_desk(refund_desk, tmp_path, capsys):
    lab, _ = _run(LAB, capsys)
    graph = build_v4_hitl(model=FakeChatModel(route="refund"))
    trace_file = tmp_path / "fresh.jsonl"
    final = lab["run_traced"](graph, "Refund order DF-1001 please", "t", "reject", trace_file)
    assert final["reply"].startswith("Refund declined for order DF-1001.")
    tools = lab["waterfall"](trace_file)
    assert tools == ["search_policy", "search_policy", "decline_refund"]
    spans = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines()]
    assert [s["kind"] for s in spans].count("run") == 1
    assert {s["parent_id"] for s in spans if s["kind"] != "run"} <= {s["id"] for s in spans}


def test_break_resume_untraced(refund_desk, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, RESUME, UNTRACED)
    _, out = _run(broken, capsys)
    assert f"reply {REPLY}" in out and "refunds_rows 1" in out
    tree = out[out.index("waterfall") + 1 :]
    assert sum(line.startswith("  chain LangGraph ") for line in tree) == 1
    assert not any(line.startswith("    chain refund ") and line.endswith(" ok") for line in tree)
    assert "tools ['search_policy']" in out
