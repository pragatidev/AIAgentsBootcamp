# %% [markdown]
# Build the TechCorp IT desk with create_agent.
#
# When this works, three tickets run through the desk with no human
# gate, and each transcript is printed message by message. The break
# returns a desk whose tool list is missing reset_password.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from techcorp.agent.desk import build_techcorp_desk, run_ticket
from techcorp.tools.accounts import grant_access, lookup_user

tickets_path = root / "techcorp" / "data" / "tickets.jsonl"
wanted = {"TC-1001", "TC-1002", "TC-1003"}
tickets = []
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if row["ticket_id"] in wanted:
        tickets.append(row)
tickets.sort(key=lambda row: row["ticket_id"])

print("model", config.CHAT_MODEL)
desk = build_techcorp_desk(middleware=[])
print("desk_type", type(desk).__name__)


def content_text(msg) -> str:
    content = getattr(msg, "content", "") or ""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return str(content)


def print_transcript(label: str, state: dict) -> None:
    print("TICKET", label)
    messages = state.get("messages") or []
    print("message_count", len(messages))
    for index, msg in enumerate(messages):
        kind = getattr(msg, "type", type(msg).__name__)
        print("hop", index, "type", kind)
        name = getattr(msg, "name", None)
        if name:
            print("name", name)
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            print("tool_calls", tool_calls)
        print("content", content_text(msg))
        print("---")
    print("final_reply", content_text(messages[-1]) if messages else "")


# %%
for row in tickets:
    text = (
        f"Ticket {row['ticket_id']} for employee {row['customer_id']}: "
        f"{row['text']}"
    )
    print("running", row["ticket_id"])
    out = run_ticket(desk, text, user_id=row["customer_id"], thread_id=row["ticket_id"])
    print_transcript(row["ticket_id"], out)

# %%
print("BREAK: desk with no reset_password tool")
broken = build_techcorp_desk(middleware=[], tools=[lookup_user, grant_access])
row = next(item for item in tickets if item["ticket_id"] == "TC-1001")
text = (
    f"Ticket {row['ticket_id']} for employee {row['customer_id']}: "
    f"{row['text']}"
)
out = run_ticket(
    broken,
    text,
    user_id=row["customer_id"],
    thread_id="break-no-reset",
)
print_transcript("TC-1001-no-reset", out)
print("returned_desk", type(broken).__name__)
