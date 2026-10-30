# %%
"""Lab 4.28: write the desk's custom middleware.

What we build: the rules a company asks for that the built-in middlewares do not carry. You type the
approver check, a write that runs only when a named person other than the requester approved it. Then
the desk keeps a run audit row with no message text, a trace with no payload, and a token budget that
ends a run with a refusal; and two built-ins stand beside them, the model call limit and PII redaction.

What you learn: a middleware is a class with hooks at fixed points around the loop. wrap_tool_call sees
every tool call before it runs, before_model and after_model see every model call, and a hook can end
the run. The human gate's decision carries no approver, a call limit counts calls and not tokens, and a
trace span still records a tool's result: those are the gaps your own middleware fills.

What will be true on your screen: the grant parked; resumed with no approver, a typed miss; resumed with
an approver, one audit line and one run audit row, neither with a secret; a reset's trace rows with the
password withheld; the tokens one ticket used and a budget below it ending the same ticket with a
refusal; the model call limit ending a run; and an email redacted before the model reads it.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware, PIIMiddleware, ToolCallLimitMiddleware
from langchain.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk, reply_text, write_gate
from techcorp.agent.middleware import RUN_AUDIT_PATH, RunAudit, TokenBudget
from techcorp.agent.trace import SafeTrace
from techcorp.agent.usage import TokenCounter
from techcorp.tools import accounts
from techcorp.tools.accounts import lookup_user


# %%
# TYPE THIS: wrap_tool_call. The class, __init__ and the docstring are given; you type the method.
# Its finished copy is ApproverRequired in techcorp/agent/middleware.py.
class ApproverRequired(AgentMiddleware):
    """A write tool runs only on a run whose envelope names an approver who is not the requester."""

    def __init__(self, write_tools=("reset_password", "grant_access")) -> None:
        super().__init__()
        self.write_tools = set(write_tools)

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        if call["name"] in self.write_tools:
            approver = (getattr(request.runtime.context, "approver", None) or "").strip()
            requester = (getattr(request.runtime.context, "user_id", None) or "").strip()
            reason = None
            if not approver:
                reason = "write needs a named approver"
            elif approver.lower() == requester.lower():
                reason = "an approver cannot approve their own request"
            if reason:
                content = json.dumps({"found": False, "reason": reason})
                return ToolMessage(content=content, tool_call_id=call["id"], name=call["name"], status="error")
        return handler(request)


# BREAK: delete the elif line and the reason line under it, and run python -m pytest tests/test_lab_05_28.py -q.
# A requester who approves their own grant now gets it written, and the test goes red. Put both lines back.

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
GRANT = "Ticket TC-1004 for employee E-4104: Please grant me read access to the finance share for Q3 close."
RESET = "Ticket TC-1001 for employee E-4101: I forgot my laptop password after the long weekend. Please reset it."


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def park_and_resume(text: str, user_id: str, thread: str, approver, callbacks=(), model=None) -> dict:
    desk = build_techcorp_desk(model=model or chat, middleware=[write_gate(), ApproverRequired(), RunAudit()], checkpointer=InMemorySaver())
    run_config = {"configurable": {"thread_id": thread}, "callbacks": list(callbacks)}
    ticket_id = text.split()[1]
    state = desk.invoke({"messages": [{"role": "user", "content": text}]}, config=run_config, context=DeskContext(user_id=user_id, ticket_id=ticket_id, request_id=thread))
    requests = state["__interrupt__"][0].value["action_requests"] if state.get("__interrupt__") else []
    print(thread, "parked_on", [request["name"] for request in requests])
    if requests:
        envelope = DeskContext(user_id=user_id, ticket_id=ticket_id, request_id=thread, approver=approver)
        state = desk.invoke(Command(resume={"decisions": [{"type": "approve"}] * len(requests)}), config=run_config, context=envelope)
    for message in state["messages"]:
        if message.type == "tool" and message.name in ("reset_password", "grant_access"):
            print(thread, "tool", message.name, message.status, message.content if message.status == "error" else "found " + str(json.loads(message.content).get("found")))
    print(thread, "reply", reply_text(state).strip())
    return state


# %%
park_and_resume(GRANT, "E-4104", "lab-4-28-no-approver", approver=None)

audit_before, runs_before = len(lines(accounts.AUDIT_PATH)), len(lines(RUN_AUDIT_PATH))
counter = TokenCounter()
park_and_resume(GRANT, "E-4104", "lab-4-28-approved", approver="E-4106", callbacks=[counter])
for line in lines(accounts.AUDIT_PATH)[audit_before:]:
    print("audit_line", line)
for line in lines(RUN_AUDIT_PATH)[runs_before:]:
    print("run_audit_row", line)

# %%
# A trace with no payload, on a reset, whose result carries the temporary password. The same model with
# its thinking off (reasoning=False) runs this one: the trace rows are the point, not the model's thoughts.
trace = SafeTrace(Path(accounts.AUDIT_PATH).parent / "traces" / "lab-4-28.jsonl")
trace.path.unlink(missing_ok=True)
quick = config.get_chat_model(reasoning=False)
state = park_and_resume(RESET, "E-4101", "lab-4-28-trace", approver="E-4106", callbacks=[trace], model=quick)
for line in lines(trace.path):
    print("trace_row", line)
passwords = [json.loads(m.content).get("temporary_password") for m in state["messages"] if m.type == "tool" and m.name == "reset_password" and m.status != "error"]
print("trace_has_password", any(p and p in trace.path.read_text(encoding="utf-8") for p in passwords))

# %%
# The budget: measure what one ticket used, then set a budget below it. DESK_TOKEN_BUDGET in .env wins.
print("measured_tokens", counter.total_tokens, "model_calls", counter.calls)
budget = config.DESK_TOKEN_BUDGET or counter.total_tokens // 2
print("budget", budget, "from", "DESK_TOKEN_BUDGET" if config.DESK_TOKEN_BUDGET else "half of the measured run")
budget_desk = build_techcorp_desk(model=chat, middleware=[write_gate(), TokenBudget(max_tokens=budget), RunAudit()], checkpointer=InMemorySaver())
out = budget_desk.invoke({"messages": [{"role": "user", "content": GRANT}]}, config={"configurable": {"thread_id": "lab-4-28-budget"}}, context=DeskContext(user_id="E-4104"))
print("budget_tokens_used", out.get("tokens_used"), "parked", bool(out.get("__interrupt__")))
print("budget_reply", reply_text(out).strip())

# %%
# Built-in beside it: ModelCallLimitMiddleware counts calls, not tokens, and ends the run at the cap.
limit_desk = build_techcorp_desk(model=chat, tools=[lookup_user], middleware=[ModelCallLimitMiddleware(run_limit=1, exit_behavior="end")])
out = limit_desk.invoke({"messages": [{"role": "user", "content": "Ticket TC-1102: look up E-4101 and E-4102 and tell me their departments."}]}, context=DeskContext(user_id="E-4101"))
print("call_limit_tools", [m.name for m in out["messages"] if m.type == "tool"])
print("call_limit_reply", reply_text(out).strip())

# %%
# Built-in beside it: PIIMiddleware redacts the email in a tool result before the model reads it.
pii_desk = build_techcorp_desk(model=chat, tools=[lookup_user], middleware=[PIIMiddleware("email", strategy="redact", apply_to_tool_results=True), ToolCallLimitMiddleware(run_limit=3)])
out = pii_desk.invoke({"messages": [{"role": "user", "content": "Ticket TC-1103 for employee E-4101: look me up and tell me my department."}]}, context=DeskContext(user_id="E-4101"))
for message in out["messages"]:
    if message.type == "tool":
        print("pii_tool_message", message.content)
print("pii_reply", reply_text(out).strip())
