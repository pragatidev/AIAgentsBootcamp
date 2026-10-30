"""Lab 05.28, ApproverRequired.wrap_tool_call typed by the student. A scripted model stands in for the real one here, and only here."""

import json
import re
import runpy
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import config
from techcorp.agent import middleware as module
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk, write_gate
from techcorp.tools import accounts
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_28_custom_middleware.py"
USAGE = {"input_tokens": 30, "output_tokens": 20, "total_tokens": 50}
CALLS = {
    "TC-1004": ("grant_access", {"user_id": "E-4104", "share": "finance-q3"}),
    "TC-1001": ("reset_password", {"user_id": "E-4101"}),
    "TC-1102": ("lookup_user", {"query": "E-4101"}),
    "TC-1103": ("lookup_user", {"query": "E-4101"}),
}


class DeskScript(BaseChatModel):
    """A human turn gets the ticket's tool call; anything after a tool result gets a sentence. Every reply costs 50 tokens."""

    model: str = "desk-script"

    @property
    def _llm_type(self) -> str:
        return "desk-script"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "DeskScript":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        ticket = re.search(r"TC-\d+", [m for m in messages if isinstance(m, HumanMessage)][-1].content).group(0)
        if isinstance(messages[-1], HumanMessage):
            name, args = CALLS[ticket]
            reply = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"{ticket}-1", "type": "tool_call"}], usage_metadata=USAGE)
        else:
            reply = AIMessage(content=f"Done: {messages[-1].content}. {ticket}", usage_metadata=USAGE)
        return ChatResult(generations=[ChatGeneration(message=reply)])


@pytest.fixture
def run_lab(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(accounts, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(module, "RUN_AUDIT_PATH", tmp_path / "run_audit.jsonl")
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: DeskScript())
    monkeypatch.setattr(config, "DESK_TOKEN_BUDGET", None)
    accounts.reload_users()

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    yield run
    accounts.reload_users()


def test_no_approver_is_a_miss_and_an_approver_writes_once(run_lab):
    _, out = run_lab()
    assert 'lab-4-28-no-approver tool grant_access error {"found": false, "reason": "write needs a named approver"}' in out
    assert "lab-4-28-approved tool grant_access success found True" in out
    audit = [json.loads(line.removeprefix("audit_line ")) for line in out if line.startswith("audit_line ")]
    assert [row["action"] for row in audit] == ["grant_access"]
    rows = [json.loads(line.removeprefix("run_audit_row ")) for line in out if line.startswith("run_audit_row ")]
    assert len(rows) == 1 and rows[0]["approver"] == "E-4106" and rows[0]["tools"] == ["grant_access"]


def test_trace_withholds_the_password(run_lab):
    _, out = run_lab()
    assert "trace_has_password False" in out
    assert any(line.startswith("trace_row ") and "temporary_password (withheld)" in line for line in out)


def test_budget_below_the_measured_run_refuses(run_lab):
    _, out = run_lab()
    assert "measured_tokens 100 model_calls 2" in out
    assert "budget 50 from half of the measured run" in out
    assert "budget_reply " + module.BUDGET_REFUSAL in out


def test_call_limit_and_pii(run_lab):
    _, out = run_lab()
    assert "call_limit_tools ['lookup_user']" in out
    pii = [line for line in out if line.startswith("pii_tool_message ")][0]
    assert "[REDACTED_EMAIL]" in pii and "amina.cole@techcorp.example" not in pii


@pytest.mark.parametrize("approver, reason", [(None, "write needs a named approver"), ("E-4104", "an approver cannot approve their own request"), ("E-4106", None)])
def test_typed_approver_check_matches_module(run_lab, tmp_path, approver, reason):
    lab, _ = run_lab()
    grant = AIMessage(content="", tool_calls=[{"name": "grant_access", "args": {"user_id": "E-4104", "share": "finance-q3"}, "id": "g", "type": "tool_call"}])
    results = []
    for cls in (lab["ApproverRequired"], module.ApproverRequired):
        accounts.reload_users()
        desk = build_techcorp_desk(model=FakeToolModel(script=[grant, "echo_tool"]), middleware=[write_gate(), cls()], checkpointer=InMemorySaver())
        cfg = {"configurable": {"thread_id": "t"}}
        desk.invoke({"messages": [HumanMessage(content="Ticket TC-1004: grant me finance-q3.")]}, config=cfg, context=DeskContext(user_id="E-4104"))
        out = desk.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=cfg, context=DeskContext(user_id="E-4104", approver=approver))
        tool = [m for m in out["messages"] if isinstance(m, ToolMessage)][0]
        results.append(json.loads(tool.content).get("reason"))
    assert results == [reason, reason]


def test_the_break_lets_a_requester_approve_their_own_grant(run_lab, tmp_path):
    old = '            elif approver.lower() == requester.lower():\n                reason = "an approver cannot approve their own request"\n'
    copy = lab_copy(LAB, tmp_path, old, "")
    lab, _ = run_lab(copy)
    accounts.reload_users()
    grant = AIMessage(content="", tool_calls=[{"name": "grant_access", "args": {"user_id": "E-4104", "share": "finance-q3"}, "id": "g", "type": "tool_call"}])
    desk = build_techcorp_desk(model=FakeToolModel(script=[grant, "echo_tool"]), middleware=[write_gate(), lab["ApproverRequired"]()], checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "t"}}
    desk.invoke({"messages": [HumanMessage(content="Ticket TC-1004: grant me finance-q3.")]}, config=cfg, context=DeskContext(user_id="E-4104"))
    out = desk.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=cfg, context=DeskContext(user_id="E-4104", approver="E-4104"))
    assert json.loads([m for m in out["messages"] if isinstance(m, ToolMessage)][0].content)["found"] is True
