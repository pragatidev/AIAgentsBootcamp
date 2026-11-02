"""Lab 03.14, read_file typed by the student. A scripted model stands in for the real one here, and only here."""

import json
import runpy
from pathlib import Path

import pytest

from dataflow.context import agent
from dataflow.context.agent import CUSTOMER_FILES
from dataflow.context.agent import read_file as shipped_read_file

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_14_just_in_time_read.py"
windows = []


def scripted_chat_caller(num_predict: int = 80, num_ctx: int | None = None, tools=None):
    windows.append(num_ctx)

    def call(messages: list) -> dict:
        ticket = next(str(m["content"]) for m in messages if m["role"] == "user").lower()
        if not tools or any(m.get("role") == "tool" for m in messages):
            return {"content": "Thirty days.", "tool_calls": [], "usage": {"input_tokens": 300}}
        name = "return_policy.md" if "return window" in ticket else "shipping.md" if "shipping" in ticket else "employee_handbook.txt"
        return {"content": "", "tool_calls": [{"id": "r1", "name": "read_file", "arguments": {"path": name}}], "usage": {"input_tokens": 200}}

    call.tool_names = [t["function"]["name"] for t in tools or []]
    return call


def scripted_context_caller(*, enable_read=True, enable_notes=True, num_ctx=None, extra_schemas=None):
    return scripted_chat_caller(num_ctx=num_ctx, tools=[agent.READ_SCHEMA] if enable_read else None)


@pytest.fixture
def run(monkeypatch):
    windows.clear()
    monkeypatch.setattr(agent, "chat_caller", scripted_chat_caller)
    monkeypatch.setattr(agent, "context_caller", scripted_context_caller)
    monkeypatch.setattr(agent, "applied_window", lambda: 16384)
    return lambda: runpy.run_path(str(LAB), run_name="__main__")


@pytest.mark.parametrize("which", ["module", "lab"])
def test_read_file_both_copies(run, which):
    read_file = shipped_read_file if which == "module" else run()["read_file"]
    assert json.loads(read_file("../../.env")) == {"found": False, "path": ".env", "reason": "unknown file"}
    assert "30 days" in json.loads(read_file("return_policy.md"))["text"]
    assert json.loads(read_file("employee_handbook.txt"))["found"] is True
    refused = json.loads(read_file("employee_handbook.txt", allowed=CUSTOMER_FILES))
    assert refused == {"found": False, "path": "employee_handbook.txt", "reason": "not on this desk's list"}
    assert json.loads(read_file("orders.json"))["text"].endswith("...[truncated]")


def test_exact_reads_and_the_refused_handbook(capsys, run):
    run()
    out = capsys.readouterr().out.splitlines()
    assert "return_ticket_reads ['return_policy.md']" in out
    assert "ship_ticket_reads ['shipping.md']" in out
    assert "read_only_on_match True" in out
    assert "handbook True" in out
    assert "open_desk_results [('employee_handbook.txt', True, None)]" in out
    assert "customer_desk_results [('employee_handbook.txt', False, \"not on this desk's list\")]" in out
    assert set(windows) == {16384}
