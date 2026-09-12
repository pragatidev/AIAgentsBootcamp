# %% [markdown]
# Human-in-the-loop middleware on the reset tool.
#
# When this works, TC-1001 parks before reset_password. The interrupt
# payload is printed. Resume with approve issues a password. Resume
# with reject does not. The break is interrupt_on={} so the reset
# does not park.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.agents.middleware import HumanInTheLoopMiddleware, ToolCallLimitMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import DEFAULT_MIDDLEWARE, build_techcorp_desk
from techcorp.tools import accounts as accounts_mod

tickets_path = root / "techcorp" / "data" / "tickets.jsonl"
ticket = None
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if row["ticket_id"] == "TC-1001":
        ticket = row
        break

print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("text", ticket["text"])
print("DEFAULT_MIDDLEWARE", DEFAULT_MIDDLEWARE)

if accounts_mod.AUDIT_PATH.exists():
    accounts_mod.AUDIT_PATH.unlink()
print("audit_path", accounts_mod.AUDIT_PATH.as_posix())

text = (
    f"Ticket {ticket['ticket_id']} for employee {ticket['customer_id']}: "
    f"{ticket['text']}"
)
ctx = DeskContext(user_id=ticket["customer_id"])
payload = {"messages": [{"role": "user", "content": text}]}

APPROVE = {"decisions": [{"type": "approve"}]}
REJECT = {"decisions": [{"type": "reject"}]}
print("resume_approve_shape", APPROVE)
print("resume_reject_shape", REJECT)


def content_text(msg) -> str:
    content = getattr(msg, "content", "") or ""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
            else:
                parts.append(str(block))
        return str("".join(parts))
    return str(content)


# %%
saver = InMemorySaver()
desk = build_techcorp_desk(
    middleware=DEFAULT_MIDDLEWARE,
    checkpointer=saver,
)
approve_cfg = {"configurable": {"thread_id": "lab-5-14-approve"}}
desk.invoke(payload, config=approve_cfg, context=ctx)
state = desk.get_state(approve_cfg)
print("thread", "lab-5-14-approve")
print("interrupts", state.interrupts)
if state.interrupts:
    print("payload", state.interrupts[0].value)
print("audit_after_park", accounts_mod.AUDIT_PATH.exists())
approved = desk.invoke(
    Command(resume=APPROVE),
    config=approve_cfg,
    context=ctx,
)
print("approve_keys", sorted(approved.keys()) if isinstance(approved, dict) else type(approved).__name__)
messages = (approved.get("messages") if isinstance(approved, dict) else None) or []
print("approve_final", content_text(messages[-1]) if messages else "")
for msg in messages:
    kind = getattr(msg, "type", type(msg).__name__)
    if "tool" in str(kind).lower():
        print("approve_tool", content_text(msg))
print("audit_after_approve", accounts_mod.AUDIT_PATH.exists())
if accounts_mod.AUDIT_PATH.exists():
    print("audit_lines", accounts_mod.AUDIT_PATH.read_text(encoding="utf-8"))

# %%
reject_cfg = {"configurable": {"thread_id": "lab-5-14-reject"}}
desk.invoke(payload, config=reject_cfg, context=ctx)
parked = desk.get_state(reject_cfg)
print("thread", "lab-5-14-reject")
print("parked_reject", bool(parked.interrupts))
if parked.interrupts:
    print("reject_payload", parked.interrupts[0].value)
before = (
    accounts_mod.AUDIT_PATH.read_text(encoding="utf-8")
    if accounts_mod.AUDIT_PATH.exists()
    else ""
)
rejected = desk.invoke(
    Command(resume=REJECT),
    config=reject_cfg,
    context=ctx,
)
rej_messages = (rejected.get("messages") if isinstance(rejected, dict) else None) or []
print("reject_final", content_text(rej_messages[-1]) if rej_messages else "")
after = (
    accounts_mod.AUDIT_PATH.read_text(encoding="utf-8")
    if accounts_mod.AUDIT_PATH.exists()
    else ""
)
print("audit_unchanged_on_reject", after == before)
print("reject_has_password", "temporary_password" in "".join(content_text(m) for m in rej_messages))
print("no password was issued on reject")

# %%
print("BREAK: interrupt_on={} so TC-1001 does not park")
open_desk = build_techcorp_desk(
    middleware=[
        HumanInTheLoopMiddleware(interrupt_on={}),
        ToolCallLimitMiddleware(run_limit=6),
    ],
    checkpointer=InMemorySaver(),
)
open_cfg = {"configurable": {"thread_id": "lab-5-14-open"}}
opened = open_desk.invoke(payload, config=open_cfg, context=ctx)
open_state = open_desk.get_state(open_cfg)
print("open_interrupts", open_state.interrupts)
open_messages = opened.get("messages") or []
print("open_final", content_text(open_messages[-1]) if open_messages else "")
for msg in open_messages:
    kind = getattr(msg, "type", type(msg).__name__)
    if "tool" in str(kind).lower():
        print("open_tool", content_text(msg))
print("parked", bool(open_state.interrupts))
