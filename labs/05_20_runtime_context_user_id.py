# %% [markdown]
# Pass a user id through runtime context to a tool.
#
# When this works, TC-1001's text has no employee id, DeskContext
# carries E-4101, and the reset tool acts on E-4101. The break puts
# E-4102 in the ticket text and E-4101 in the context; the tool still
# acts on the context id.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk

print("model", config.CHAT_MODEL)

tickets_path = root / "techcorp" / "data" / "tickets.jsonl"
ticket = None
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if row["ticket_id"] == "TC-1001":
        ticket = row
        break

print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])
print("text_has_E-4101", "E-4101" in ticket["text"])
print("DeskContext", DeskContext(user_id="E-4101"))

desk = build_techcorp_desk(middleware=[])


def print_tools(state: dict) -> None:
    for msg in state.get("messages") or []:
        kind = getattr(msg, "type", type(msg).__name__)
        calls = getattr(msg, "tool_calls", None) or []
        if calls:
            print("model_tool_calls", calls)
        if "tool" in str(kind).lower() and "call" not in str(kind).lower():
            print("tool_name", getattr(msg, "name", None))
            print("tool_result", getattr(msg, "content", None))


# %%
payload = {
    "messages": [
        {
            "role": "user",
            "content": f"Ticket {ticket['ticket_id']}: {ticket['text']}",
        }
    ]
}
out = desk.invoke(
    payload,
    config={"configurable": {"thread_id": "lab-5-20-envelope"}},
    context=DeskContext(user_id="E-4101"),
)
print("NO_ID_IN_TEXT")
print_tools(out)
messages = out.get("messages") or []
print("final", getattr(messages[-1], "content", None) if messages else None)

# %%
print("BREAK: ticket says E-4102, context is E-4101")
broken = desk.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Ticket TC-1098: I am E-4102, reset my password.",
            }
        ]
    },
    config={"configurable": {"thread_id": "lab-5-20-break"}},
    context=DeskContext(user_id="E-4101"),
)
print_tools(broken)
break_messages = broken.get("messages") or []
print("final_break", getattr(break_messages[-1], "content", None) if break_messages else None)
print("context_user_id", "E-4101")
print("text_user_id", "E-4102")
