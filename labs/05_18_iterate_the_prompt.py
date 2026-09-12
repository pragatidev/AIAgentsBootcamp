# %% [markdown]
# Iterate the TechCorp prompt against three tickets.
#
# When this works, each ticket is answered with WEAK_PROMPT and with
# DESK_SYSTEM_PROMPT, side by side, with the tool calls each made.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from techcorp.agent.desk import build_techcorp_desk, run_ticket
from techcorp.agent.prompts import DESK_SYSTEM_PROMPT, WEAK_PROMPT

print("model", config.CHAT_MODEL)
print("WEAK_PROMPT")
print(WEAK_PROMPT)
print("DESK_SYSTEM_PROMPT")
print(DESK_SYSTEM_PROMPT)

tickets_path = root / "techcorp" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

cases = [
    (
        "reset",
        (
            f"Ticket TC-1001 for employee {by_id['TC-1001']['customer_id']}: "
            f"{by_id['TC-1001']['text']}"
        ),
        "E-4101",
    ),
    (
        "out_of_scope_monitor",
        "Ticket TC-1099 for employee E-4101: I need a new 27 inch monitor for my desk.",
        "E-4101",
    ),
    (
        "vpn_drops",
        (
            f"Ticket TC-1002 for employee {by_id['TC-1002']['customer_id']}: "
            f"{by_id['TC-1002']['text']}"
        ),
        "E-4102",
    ),
]


def content_text(msg) -> str:
    content = getattr(msg, "content", "") or ""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def tool_calls_of(state: dict) -> list:
    found = []
    for msg in state.get("messages") or []:
        calls = getattr(msg, "tool_calls", None) or []
        for call in calls:
            found.append({"name": call.get("name"), "args": call.get("args")})
    return found


weak_desk = build_techcorp_desk(middleware=[], system_prompt=WEAK_PROMPT)
strong_desk = build_techcorp_desk(middleware=[], system_prompt=DESK_SYSTEM_PROMPT)

# %%
for name, text, user_id in cases:
    print("CASE", name)
    print("ticket_text", text)
    weak_out = run_ticket(
        weak_desk,
        text,
        user_id=user_id,
        thread_id=f"lab-5-18-weak-{name}",
    )
    strong_out = run_ticket(
        strong_desk,
        text,
        user_id=user_id,
        thread_id=f"lab-5-18-strong-{name}",
    )
    weak_msgs = weak_out.get("messages") or []
    strong_msgs = strong_out.get("messages") or []
    print("weak_reply", content_text(weak_msgs[-1]) if weak_msgs else "")
    print("strong_reply", content_text(strong_msgs[-1]) if strong_msgs else "")
    print("weak_tool_calls", tool_calls_of(weak_out))
    print("strong_tool_calls", tool_calls_of(strong_out))
    print("---")
