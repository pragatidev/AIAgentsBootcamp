"""The desk's own middleware and the built-ins Section 4 adds, each on a known answer. No live model."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk, run_ticket, write_gate
from techcorp.agent.middleware import BUDGET_REFUSAL, ApproverRequired, RunAudit, TokenBudget
from techcorp.agent.trace import SafeTrace
from techcorp.tools import accounts
from techcorp.tools.accounts import lookup_user, reset_password
from tests.fixtures.fake_model import FakeToolModel, ScriptedToolChatModel


@pytest.fixture(autouse=True)
def audit(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts, "AUDIT_PATH", path)
    accounts.reload_users()
    yield path
    accounts.reload_users()


def _ask(name: str, args: dict, call_id: str, usage: dict | None = None) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}], usage_metadata=usage)


GRANT = _ask("grant_access", {"user_id": "E-4104", "share": "finance-q3"}, "g1")


def _gated(model, tmp_path, **extra):
    return build_techcorp_desk(
        model=model,
        middleware=[write_gate(), ApproverRequired(), RunAudit(tmp_path / "run_audit.jsonl"), *extra.get("more", [])],
        checkpointer=InMemorySaver(),
    )


def _park_then_resume(desk, approver):
    cfg = {"configurable": {"thread_id": "t"}}
    ctx = DeskContext(user_id="E-4104", ticket_id="TC-1004", request_id="req-1")
    parked = desk.invoke({"messages": [HumanMessage(content="Ticket TC-1004: grant me finance-q3.")]}, config=cfg, context=ctx)
    assert parked["__interrupt__"]
    ctx = DeskContext(user_id="E-4104", ticket_id="TC-1004", request_id="req-1", approver=approver)
    return desk.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=cfg, context=ctx)


def test_resume_without_approver_is_a_miss(audit, tmp_path):
    out = _park_then_resume(_gated(FakeToolModel(script=[GRANT, "echo_tool"]), tmp_path), approver=None)
    tool = [m for m in out["messages"] if m.type == "tool"][0]
    assert json.loads(tool.content) == {"found": False, "reason": "write needs a named approver"}
    assert not audit.exists()


def test_approver_cannot_approve_own_request(audit, tmp_path):
    out = _park_then_resume(_gated(FakeToolModel(script=[GRANT, "echo_tool"]), tmp_path), approver="E-4104")
    tool = [m for m in out["messages"] if m.type == "tool"][0]
    assert json.loads(tool.content)["reason"] == "an approver cannot approve their own request"
    assert not audit.exists()


def test_resume_with_approver_writes_one_line(audit, tmp_path):
    out = _park_then_resume(_gated(FakeToolModel(script=[GRANT, "echo_tool"]), tmp_path), approver="E-4106")
    assert json.loads([m for m in out["messages"] if m.type == "tool"][0].content)["found"] is True
    lines = audit.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["action"] == "grant_access"
    rows = (tmp_path / "run_audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert (row["user_id"], row["approver"], row["ticket_id"], row["request_id"]) == ("E-4104", "E-4106", "TC-1004", "req-1")
    assert row["tools"] == ["grant_access"] and row["outcome"] == "replied"


def test_run_audit_row_has_no_message_text(audit, tmp_path):
    _park_then_resume(_gated(FakeToolModel(script=[GRANT, "echo_tool"]), tmp_path), approver="E-4106")
    row = (tmp_path / "run_audit.jsonl").read_text(encoding="utf-8")
    assert "grant me finance-q3" not in row and "Done." not in row
    assert set(json.loads(row)) == {"request_id", "ticket_id", "user_id", "approver", "tools", "tokens_used", "outcome", "at"}


def test_token_budget_ends_the_run(audit, tmp_path):
    usage = {"input_tokens": 60, "output_tokens": 40, "total_tokens": 100}
    script = [
        _ask("lookup_user", {"query": "E-4101"}, "a", usage),
        _ask("reset_password", {"user_id": "E-4101"}, "b", usage),
        AIMessage(content="never reached"),
    ]
    desk = build_techcorp_desk(model=FakeToolModel(script=script), middleware=[TokenBudget(max_tokens=150), RunAudit(tmp_path / "run_audit.jsonl")])
    out = run_ticket(desk, "Ticket TC-1001: reset it.", user_id="E-4101")
    assert out["messages"][-1].content == BUDGET_REFUSAL
    assert out["tokens_used"] == 200
    assert [m.name for m in out["messages"] if m.type == "tool"] == ["lookup_user"]
    assert not audit.exists()
    row = json.loads((tmp_path / "run_audit.jsonl").read_text(encoding="utf-8"))
    assert row["outcome"] == "budget_refusal" and row["tokens_used"] == 200


def test_token_budget_absent_usage_counts_zero(tmp_path):
    desk = build_techcorp_desk(model=FakeToolModel(script=[_ask("lookup_user", {"query": "E-4101"}, "a"), AIMessage(content="Found. TC-1001")]), middleware=[TokenBudget(max_tokens=1)])
    out = run_ticket(desk, "Ticket TC-1001: who am I?", user_id="E-4101")
    assert out["tokens_used"] == 0 and out["messages"][-1].content == "Found. TC-1001"


def test_trace_row_has_no_secret(tmp_path):
    reset = _ask("reset_password", {"user_id": "E-4101"}, "r")
    model = ScriptedToolChatModel(script=[reset, AIMessage(content="Done. TC-1001")])
    desk = build_techcorp_desk(model=model, tools=[reset_password], middleware=[])
    trace = SafeTrace(tmp_path / "trace.jsonl")
    out = desk.invoke({"messages": [HumanMessage(content="Ticket TC-1001: reset it.")]}, config={"callbacks": [trace]}, context=DeskContext(user_id="E-4101"))
    password = json.loads([m for m in out["messages"] if m.type == "tool"][0].content)["temporary_password"]
    text = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert password not in text
    tool_row = [json.loads(line) for line in text.splitlines() if '"kind": "tool"' in line][0]
    assert tool_row["tool"] == "reset_password"
    assert "temporary_password (withheld)" in tool_row["result_keys"]


def test_lookup_email_redacted_before_model():
    from langchain.agents.middleware import PIIMiddleware

    script = [_ask("lookup_user", {"query": "E-4101"}, "a"), AIMessage(content="Found. TC-1001")]
    desk = build_techcorp_desk(model=FakeToolModel(script=script), tools=[lookup_user], middleware=[PIIMiddleware("email", strategy="redact", apply_to_tool_results=True)])
    out = run_ticket(desk, "Ticket TC-1001: who am I?", user_id="E-4101")
    tool = [m for m in out["messages"] if m.type == "tool"][0]
    assert "amina.cole@techcorp.example" not in tool.content
    assert "[REDACTED_EMAIL]" in tool.content


def test_model_call_limit_ends_run():
    from langchain.agents.middleware import ModelCallLimitMiddleware

    script = [_ask("lookup_user", {"query": "E-4101"}, "a"), _ask("lookup_user", {"query": "E-4102"}, "b"), AIMessage(content="never")]
    desk = build_techcorp_desk(model=FakeToolModel(script=script), tools=[lookup_user], middleware=[ModelCallLimitMiddleware(run_limit=1, exit_behavior="end")])
    out = run_ticket(desk, "Ticket TC-1102: look up two people.", user_id="E-4101")
    assert [m.name for m in out["messages"] if m.type == "tool"] == ["lookup_user"]
    assert "limit" in str(out["messages"][-1].content).lower()
