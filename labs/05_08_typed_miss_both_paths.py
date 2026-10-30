# %%
"""Lab 4.8: return a typed miss and test both paths.

What we build: you write the few lines inside the reset tool that decide between "here is the
password" and "I could not do that", run them on a real employee, on a ghost and on an empty id, test
both paths, and then hand a ghost ticket to the real desk and read what the model says.

What you learn: a miss is data, found False and a reason, not an exception and not a sentence. A tool
that cannot find a user never invents one, and the model reads the miss as a tool message and tells the
employee.

What will be true on your screen: known with found True and a pretend temporary password, unknown with
found False and the reason "unknown user E-9999", empty with "no user id"; then the desk's tool messages
for ticket TC-1099 and its reply. Run python -m pytest tests/test_lab_05_08.py -q to test both paths.
"""

from pathlib import Path
from typing import Any
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool

import config
from techcorp.agent.desk import build_techcorp_desk, reply_text, run_ticket
from techcorp.tools.accounts import _context_user_id, _find_user, _temporary_password, lookup_user, reset_password


# %%
# TYPE THIS: reset_outcome. The signature and docstring are given; you type the body.
# Its finished copy is in techcorp/tools/accounts.py, where reset_password calls it.
def reset_outcome(acting: str) -> dict:
    """The miss shape, found False and a reason, for an empty or unknown id; the hit shape for a known one. Never invent a user."""
    if not acting:
        return {"found": False, "reason": "no user id"}
    row = _find_user(acting)
    if not row:
        return {"found": False, "reason": f"unknown user {acting}"}
    return {
        "found": True,
        "user_id": row["user_id"],
        "temporary_password": _temporary_password(),
        "expires_in_hours": 24,
    }


# BREAK: in the unknown-id branch above, return
# {"found": True, "user_id": acting, "temporary_password": "invented01", "expires_in_hours": 24}
# instead of the miss, then run python -m pytest tests/test_lab_05_08.py -q and read the red line.
# Put the miss back and run the test again.

print("known", reset_outcome("E-4101"))
print("unknown", reset_outcome("E-9999"))
print("empty", reset_outcome(""))


# %%
# Given, not typed: the desk's reset tool with your reset_outcome inside. It reads the account from
# the request envelope, never from the id the model typed, and writes no audit line.
@tool("reset_password", description=reset_password.description)
def lab_reset_password(user_id: str, runtime: ToolRuntime[Any]) -> dict:
    return reset_outcome(_context_user_id(runtime) or "")


# %%
# The real model reads your miss. The ghost id rides in the envelope, so the miss does not depend on
# the id the model types. No grant tool here, and nothing a ghost asks for can be written.
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
desk = build_techcorp_desk(model=chat, middleware=[], tools=[lookup_user, lab_reset_password])
state = run_ticket(desk, "Ticket TC-1099: please reset the password for E-9999.", user_id="E-9999")
for message in state["messages"]:
    if isinstance(message, ToolMessage):
        print("tool", message.name, message.content)
print("reply", reply_text(state).strip())
