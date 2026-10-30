"""The desk's own middleware: rules a company needs that the built-ins do not carry.

ApproverRequired: a write runs only when a named person, not the requester, approved it.
TokenBudget: a run that has spent its token budget ends with a refusal instead of a bigger bill.
RunAudit: one row per run with ids, tools and tokens, never the text of a message.
PermissionGate: a call the caller's role or region does not allow never reaches a person or a tool.
region_prompt: the system prompt names the region the desk serves, read from the envelope.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, dynamic_prompt, hook_config
from langchain_core.messages import AIMessage, RemoveMessage, ToolMessage
from typing_extensions import NotRequired

from techcorp.agent import permissions
from techcorp.agent.prompts import DESK_SYSTEM_PROMPT
from techcorp.agent.usage import read_usage

WRITES = ("reset_password", "grant_access")
RUN_AUDIT_PATH = Path(__file__).resolve().parents[1] / "data" / "run_audit.jsonl"
BUDGET_REFUSAL = "I cannot finish this ticket inside its token budget. Please contact the IT desk lead."


def _context_value(runtime: Any, key: str) -> Any:
    ctx = getattr(runtime, "context", None)
    if ctx is None:
        return None
    return ctx.get(key) if isinstance(ctx, dict) else getattr(ctx, key, None)


class ApproverRequired(AgentMiddleware):
    """A write tool runs only on a run whose envelope names an approver who is not the requester."""

    def __init__(self, write_tools=WRITES) -> None:
        super().__init__()
        self.write_tools = set(write_tools)

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        if call["name"] in self.write_tools:
            approver = (_context_value(request.runtime, "approver") or "").strip()
            requester = (_context_value(request.runtime, "user_id") or "").strip()
            reason = None
            if not approver:
                reason = "write needs a named approver"
            elif approver.lower() == requester.lower():
                reason = "an approver cannot approve their own request"
            if reason:
                content = json.dumps({"found": False, "reason": reason})
                return ToolMessage(content=content, tool_call_id=call["id"], name=call["name"], status="error")
        return handler(request)


class BudgetState(AgentState):
    tokens_used: NotRequired[int]


class TokenBudget(AgentMiddleware):
    """Count every model call's tokens in the run; once the run reaches max_tokens, end it with a refusal."""

    state_schema = BudgetState

    def __init__(self, max_tokens: int) -> None:
        super().__init__()
        self.max_tokens = int(max_tokens)

    def before_agent(self, state, runtime) -> dict[str, Any]:
        return {"tokens_used": 0}

    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime) -> dict[str, Any] | None:
        if state.get("tokens_used", 0) >= self.max_tokens:
            return {"jump_to": "end", "messages": [AIMessage(content=BUDGET_REFUSAL)]}
        return None

    @hook_config(can_jump_to=["end"])
    def after_model(self, state, runtime) -> dict[str, Any] | None:
        last = state["messages"][-1]
        used = state.get("tokens_used", 0) + (read_usage(last)["total_tokens"] if isinstance(last, AIMessage) else 0)
        if used < self.max_tokens:
            return {"tokens_used": used}
        # Over budget: the tools this reply asked for never run, and the run ends on the refusal.
        updates: list[Any] = [AIMessage(content=BUDGET_REFUSAL)]
        if isinstance(last, AIMessage) and last.tool_calls:
            updates.insert(0, RemoveMessage(id=last.id))
        return {"tokens_used": used, "jump_to": "end", "messages": updates}


class RunState(AgentState):
    run_start: NotRequired[int]


class RunAudit(AgentMiddleware):
    """One row per run in run_audit.jsonl: request, ticket, caller, approver, tools, tokens and outcome. Never message text."""

    state_schema = RunState

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self.path = Path(path) if path is not None else None

    def before_agent(self, state, runtime) -> dict[str, Any]:
        return {"run_start": len(state["messages"])}

    def after_agent(self, state, runtime) -> None:
        messages = state["messages"][state.get("run_start", 0):]
        tools = [m.name for m in messages if isinstance(m, ToolMessage)]
        last = messages[-1] if messages else None
        text = last.text if isinstance(last, AIMessage) else ""
        outcome = "budget_refusal" if text == BUDGET_REFUSAL else "replied" if text.strip() else "empty_reply"
        row = {
            "request_id": _context_value(runtime, "request_id"),
            "ticket_id": _context_value(runtime, "ticket_id"),
            "user_id": _context_value(runtime, "user_id"),
            "approver": _context_value(runtime, "approver"),
            "tools": tools,
            "tokens_used": state.get("tokens_used"),
            "outcome": outcome,
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        path = self.path or RUN_AUDIT_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
        return None


class PermissionGate(AgentMiddleware):
    """Check every proposed tool call against the rules before a person or a tool sees it, and again when it runs.

    List it after write_gate(): after_model hooks run from the last in the list to the first, so this one
    answers a refused call with a typed miss first. When every call in the turn is refused, the run jumps
    back to the model, past the human gate, so nothing parks and the model reads the misses. A turn that
    mixes allowed and refused calls goes on to the gate, and only the allowed calls run. wrap_tool_call
    checks again at execution, because an edit decision can change the arguments after the park.
    """

    def __init__(self, checker=None) -> None:
        super().__init__()
        self.checker = checker or permissions.check

    @hook_config(can_jump_to=["model"])
    def after_model(self, state, runtime) -> dict[str, Any] | None:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None
        refused = []
        for call in last.tool_calls:
            miss = self.checker(call["name"], call.get("args") or {}, runtime.context)
            if miss is not None:
                refused.append(ToolMessage(content=json.dumps(miss), tool_call_id=call["id"], name=call["name"], status="error"))
        if not refused:
            return None
        # The calls stay on the AI message and each refused one gets its answer, so the pairing holds.
        update: dict[str, Any] = {"messages": refused}
        if len(refused) == len(last.tool_calls):
            update["jump_to"] = "model"
        return update

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        miss = self.checker(call["name"], call.get("args") or {}, request.runtime.context)
        if miss is not None:
            return ToolMessage(content=json.dumps(miss), tool_call_id=call["id"], name=call["name"], status="error")
        return handler(request)


@dynamic_prompt
def region_prompt(request) -> str:
    """The desk's prompt plus one line naming the region the envelope says this desk serves."""
    region = getattr(request.runtime.context, "region", None) or "US"
    return DESK_SYSTEM_PROMPT + f"\nTenant rules: this desk serves the {region} region only. Employees in another region use their own region's desk.\n"
