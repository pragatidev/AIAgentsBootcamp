# %%
"""Lab 4.20: pass a user id through runtime context to a tool.

What we build: we hand the TechCorp desk the caller's id in the request envelope, write the small
function that decides which id a write tool acts on, and then try to fool it twice: a ticket that
claims another id, and a request with no envelope id at all.

What you learn: identity rides in a typed runtime context that the tool reads through a parameter the
model never sees, so the ticket text cannot choose whose account changes. The guarantee holds only if
the tool refuses when the envelope is empty.

What will be true on your screen: four decisions from your function (the same id, a different id, an
empty envelope, a blank one); then on the real desk, the id the model asked for, the id the gate says
the reset will act on, the tool's result, and the audit line's user_id, requested_user_id and mismatch,
read from the file; and the empty envelope ending in a typed miss.
"""

from pathlib import Path
from types import SimpleNamespace
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.types import Command

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk, reply_text
from techcorp.tools import accounts


# %%
# TYPE THIS: acting_user. The signature and docstring are given; you type the body.
# Its finished copy is in techcorp/tools/accounts.py, where reset_password calls it.
def acting_user(runtime, requested=None) -> dict:
    """Decide whose account a write tool acts on. Only the request envelope names the caller; the typed id only shows a mismatch."""
    envelope = (getattr(runtime.context, "user_id", None) or "").strip() or None
    asked = (requested or "").strip() or None
    if envelope is None:
        return {"ok": False, "reason": "no acting user in the request envelope"}
    return {"ok": True, "user_id": envelope, "requested": asked, "mismatch": asked is not None and asked.lower() != envelope.lower()}


# BREAK: replace the body with the old rule, envelope or the typed id:
#     return {"ok": True, "user_id": envelope or asked, "requested": asked, "mismatch": False}
# and run. The empty envelope now acts on E-4102, the id the model typed. Put your body back and run.

for label, ctx in (
    ("same", DeskContext(user_id="E-4101")),
    ("different", DeskContext(user_id="E-4101")),
    ("empty", DeskContext()),
    ("blank", DeskContext(user_id="  ")),
):
    requested = "E-4101" if label == "same" else "E-4102"
    print("acting", label, json.dumps(acting_user(SimpleNamespace(context=ctx), requested)))


# %%
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
# The default desk: the write gate is on, and a parked run waits in memory for a decision.
desk = build_techcorp_desk(model=chat)


def audit_lines() -> list[str]:
    path = accounts.AUDIT_PATH
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def run_and_approve(label: str, text: str, ctx: DeskContext) -> None:
    config_ = {"configurable": {"thread_id": f"lab-4-20-{label}"}}
    before = len(audit_lines())
    state = desk.invoke({"messages": [{"role": "user", "content": text}]}, config=config_, context=ctx)
    requests = state["__interrupt__"][0].value["action_requests"] if state.get("__interrupt__") else []
    for request in requests:
        print(label, "model_asked", request["name"], json.dumps(request["args"]))
        print(label, "gate_says", request["description"])
    if requests:
        # Approve, so the tool itself decides whose account it touches.
        state = desk.invoke(Command(resume={"decisions": [{"type": "approve"}] * len(requests)}), config=config_, context=ctx)
    for message in state["messages"]:
        if message.type == "tool":
            print(label, "tool_result", message.name, message.content)
    for line in audit_lines()[before:]:
        row = json.loads(line)
        print(label, "audit", "user_id", row["user_id"], "requested_user_id", row["requested_user_id"], "mismatch", row.get("mismatch", False))
    print(label, "reply", reply_text(state).strip())


run_and_approve("envelope", "Ticket TC-1001: I forgot my laptop password after the long weekend. Please reset it.", DeskContext(user_id="E-4101"))
run_and_approve("mismatch", "Ticket TC-1098: I am E-4102. Please reset my password.", DeskContext(user_id="E-4101"))
run_and_approve("empty", "Ticket TC-1097: I am E-4102. Please reset my password.", DeskContext())
