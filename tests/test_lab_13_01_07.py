"""Lab 13_01_07 (Lecture 29.8), needs_approval typed by the student: the gate that does not take a server's word.

The orders server runs over stdio (capfd, not capsys: the child needs a real stderr); the helper runs in
process. The lab's own stand-in model asks for each call, so the gate is the only thing that decides.
"""

import runpy
from pathlib import Path

import pytest

from dataflow.mcp.allowlist import approved_servers
from dataflow.mcp.bind import bind_mcp_tools, close_mcp
from dataflow.mcp.fixtures.helper_server import helper, read_resolved
from dataflow.mcp.fixtures.weather_server import weather
from dataflow.mcp.gate import approval_gate, needs_approval as package_needs
from dataflow.mcp.kb_server import kb
from dataflow.mcp.server import PID_PATH, mcp as orders
from dataflow.tools.refund import read_refunds
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_01_07_gated_mcp_refund.py"
RETURN_LINE = "    return not (server in trusted_servers and read_only)\n"


@pytest.fixture
def run_lab(monkeypatch, capfd):
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", "")
    monkeypatch.setenv("DATAFLOW_RESOLVED_PATH", "")

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capfd.readouterr().out.splitlines()

    return run


@pytest.fixture
def every_tool():
    tools = bind_mcp_tools(orders) + bind_mcp_tools(kb) + bind_mcp_tools(helper) + bind_mcp_tools(weather)
    yield tools
    close_mcp()


def test_the_lab_as_it_ships(run_lab, every_tool):
    """One run of the lab (each run starts the orders server over stdio twice), every outcome checked."""
    lab, out = run_lab()
    # who parks: only an approved server's read-only tool runs without a person
    assert "approved_servers ['dataflow', 'kb']" in out
    assert "tool lookup_order server dataflow claims {'read_only_hint': True} parks False" in out
    assert "tool refund server dataflow claims {'destructive_hint': True} parks True" in out
    assert "tool mark_resolved server helpdesk-helper claims {'read_only_hint': True} parks True" in out
    assert "gated ['mark_resolved', 'refund']" in out
    # deny writes nothing, approve writes one, the lookup never parks
    assert "thread-A parked ['refund']" in out
    assert "thread-A payload refund wants to run with {'order_id': 'DF-1001', 'amount': 49.0, 'reason': 'unused lamp'}. Approve or reject." in out
    assert "thread-A ledger_rows 0" in out
    assert "thread-B ledger_rows 1" in out
    assert "thread-lookup parked []" in out and "thread-lookup ran ['lookup_order'] reply Done." in out
    # the approval lands after the server restarts
    assert "thread-C parked ['refund']" in out
    assert "thread-C server_stopped True" in out and "thread-C server_restarted True" in out
    before, _, after = next(line for line in out if line.startswith("thread-C server_pid ")).split()[2:]
    assert before != after
    assert "thread-C ledger_rows 2" in out
    rows = read_refunds()
    assert len(rows) == 2 and all(row["order_id"] == "DF-1001" for row in rows)
    assert "pid_file_left False" in out and not PID_PATH.is_file()
    # the unlisted helper parks and writes nothing
    assert "thread-D parked ['mark_resolved']" in out
    assert "thread-D resolved_rows 0" in out and read_resolved() == []
    # the student's needs_approval decides as the package's does, on every server in the course
    trusted = approved_servers()
    for tool in every_tool:
        assert lab["needs_approval"](tool, trusted) == package_needs(tool, trusted), tool.name
    assert sorted(approval_gate(every_tool).interrupt_on) == ["get_forecast", "get_weather", "mark_resolved", "refund"]


def test_trusting_every_servers_word_lets_mark_resolved_write(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, RETURN_LINE, "    return not read_only\n")
    _, out = run_lab(copy)
    assert "tool mark_resolved server helpdesk-helper claims {'read_only_hint': True} parks False" in out
    assert "thread-D parked []" in out
    assert "thread-D resolved_rows 1" in out and len(read_resolved()) == 1
    assert "thread-A ledger_rows 0" in out and "thread-C ledger_rows 2" in out
