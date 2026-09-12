# %% [markdown]
# Break for lab 6.14: reject the parked reset with a message.
#
# The desk parks before reset_password. The reviewer resumes with a reject
# decision that carries a message. The middleware turns that message into
# the tool's result, and the model writes the refusal shape. The audit file
# stays absent because the reset never ran.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from techcorp.agent.context import DeskContext
from techcorp.agent.desk import DEFAULT_MIDDLEWARE, build_techcorp_desk
from techcorp.tools import accounts as a

if a.AUDIT_PATH.exists():
    a.AUDIT_PATH.unlink()

desk = build_techcorp_desk(middleware=DEFAULT_MIDDLEWARE, checkpointer=InMemorySaver())
ctx = DeskContext(user_id="E-4101")
cfg = {"configurable": {"thread_id": "lab-5-14-reject-with-message"}}

# %%
desk.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Ticket TC-1001 for employee E-4101: I forgot my laptop password after the long weekend. Please reset it.",
            }
        ]
    },
    config=cfg,
    context=ctx,
)
print("parked", bool(desk.get_state(cfg).interrupts))

# %%
out = desk.invoke(
    Command(
        resume={
            "decisions": [
                {"type": "reject", "message": "Reviewer rejected the reset: identity not verified."}
            ]
        }
    ),
    config=cfg,
    context=ctx,
)
msgs = out.get("messages") or []
print("reject_with_message_final", repr(getattr(msgs[-1], "content", "")))
print("last_types", [getattr(m, "type", "") for m in msgs[-3:]])
print("audit_exists", a.AUDIT_PATH.exists())
