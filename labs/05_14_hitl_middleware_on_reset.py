# %%
"""Lab 4.14: human-in-the-loop middleware on the reset tool.

What we build: we put a person in front of every write the desk can make. You type the gate: the
desk's write tools, reset_password and grant_access, each one parking the run until someone decides.
Then a reset ticket parks, you approve one thread and reject two others, a grant ticket parks too, and
a typo in your gate lets a reset straight through.

What you learn: middleware changes the loop without owning it, and human in the loop is a policy
written as a list of tool names. The gate is only as good as that list, so every write tool goes on it
and a test checks the names.

What will be true on your screen: the gate's tool names and its four choices (approve, edit, reject,
respond); a parked reset whose description names the employee the reset will act on; no audit line
while parked; after approve, one audit line with no password in it; for each reject, the tool message
the model was given, whether it asked again (and parked again), and its reply; and a parked grant.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig, ToolCallLimitMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk, describe_write, reply_text, run_ticket
from techcorp.tools import accounts


# %%
# TYPE THIS: write_gate. The signature and docstring are given; you type the body.
# Its finished copy is in techcorp/agent/desk.py, inside DEFAULT_MIDDLEWARE.
def write_gate() -> HumanInTheLoopMiddleware:
    """Park the run before every write tool until a person decides; the description names the id the tool acts on."""
    return HumanInTheLoopMiddleware(
        interrupt_on={
            name: InterruptOnConfig(allowed_decisions=["approve", "edit", "reject", "respond"], description=describe_write)
            for name in ("reset_password", "grant_access")
        }
    )


# BREAK: misspell "reset_password" as "reset_pasword" in the tuple above and run. Nothing parks, the
# reset runs at once and writes its audit line, and python -m pytest tests/test_lab_05_14.py -q goes red
# on the gate's names. Fix the spelling and run.

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
gate = write_gate()
for name, rule in gate.interrupt_on.items():
    print("gated", name, rule["allowed_decisions"])

# The saver keeps a parked run in memory; the thread id names which run to resume.
desk = build_techcorp_desk(model=chat, middleware=[gate, ToolCallLimitMiddleware(run_limit=6)], checkpointer=InMemorySaver())
RESET = "Ticket TC-1001 for employee E-4101: I forgot my laptop password after the long weekend. Please reset it."


def audit_lines() -> list[str]:
    path = accounts.AUDIT_PATH
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def park(text: str, thread: str, user_id: str) -> list:
    state = run_ticket(desk, text, user_id=user_id, thread_id=thread)
    requests = state["__interrupt__"][0].value["action_requests"] if state.get("__interrupt__") else []
    print(thread, "parked", bool(requests))
    for request in requests:
        print(thread, "parked_on", request["name"], json.dumps(request["args"]))
        print(thread, "description", request["description"])
    if not requests:
        print(thread, "reply", reply_text(state).strip())
    return requests


def resume(thread: str, user_id: str, decision: dict, count: int) -> dict:
    # Command(resume=...) carries the person's answer back into the parked run, one decision per parked call.
    return desk.invoke(
        Command(resume={"decisions": [decision] * count}),
        config={"configurable": {"thread_id": thread}},
        context=DeskContext(user_id=user_id),
    )


# %%
before = len(audit_lines())
requests = park(RESET, "lab-4-14-approve", "E-4101")
print("audit_lines_after_park", len(audit_lines()) - before)
if requests:
    out = resume("lab-4-14-approve", "E-4101", {"type": "approve"}, len(requests))
    print("approve_parked_again", bool(out.get("__interrupt__")))
    print("approve_reply", reply_text(out).strip())
    added = audit_lines()[before:]
    print("audit_lines_after_approve", len(added))
    for line in added:
        print("audit_line", line)
    print("audit_has_password", any("temporary_password" in line for line in added))

# %%
for thread, decision in (
    ("lab-4-14-reject", {"type": "reject"}),
    ("lab-4-14-reject-reason", {"type": "reject", "message": "Reviewer rejected the reset: identity not verified."}),
):
    before = len(audit_lines())
    requests = park(RESET, thread, "E-4101")
    if requests:
        out = resume(thread, "E-4101", decision, len(requests))
        # The reject comes back to the model as a tool message with status error, in place of the result.
        told = [m for m in out["messages"] if m.type == "tool" and m.status == "error"][0]
        print(thread, "tool_message_status", told.status)
        print(thread, "tool_message", told.content)
        print(thread, "parked_again", bool(out.get("__interrupt__")))
        print(thread, "reply", reply_text(out).strip())
        print(thread, "audit_lines_added", len(audit_lines()) - before)

# %%
GRANT = "Ticket TC-1004 for employee E-4104: Please grant me read access to the finance share for Q3 close."
requests = park(GRANT, "lab-4-14-grant", "E-4104")
print("grant_parked", any(r["name"] == "grant_access" for r in requests))
if requests:
    out = resume("lab-4-14-grant", "E-4104", {"type": "reject", "message": "Grants wait for the share owner."}, len(requests))
    print("grant_parked_again", bool(out.get("__interrupt__")))
    print("grant_reply", reply_text(out).strip())
