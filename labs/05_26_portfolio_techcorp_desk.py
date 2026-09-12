# %% [markdown]
# Portfolio: TechCorp IT desk v1 with README.
#
# When this works, the final desk runs three tickets (reset parks then
# approve, VPN answers, out of scope refuses in the fixed shape) and
# pytest is green. Read techcorp/README.md for how to clone and run.

# %%
from pathlib import Path
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import DEFAULT_MIDDLEWARE, build_techcorp_desk
from techcorp.tools import accounts as accounts_mod

print("model", config.CHAT_MODEL)
print("readme", (root / "techcorp" / "README.md").is_file())
print( (root / "techcorp" / "README.md").read_text(encoding="utf-8")[:400] )

if accounts_mod.AUDIT_PATH.exists():
    accounts_mod.AUDIT_PATH.unlink()

tickets_path = root / "techcorp" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

saver = InMemorySaver()
desk = build_techcorp_desk(
    middleware=DEFAULT_MIDDLEWARE,
    checkpointer=saver,
)
APPROVE = {"decisions": [{"type": "approve"}]}


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


# %%
reset_row = by_id["TC-1001"]
reset_text = (
    f"Ticket {reset_row['ticket_id']} for employee {reset_row['customer_id']}: "
    f"{reset_row['text']}"
)
reset_cfg = {"configurable": {"thread_id": "lab-5-26-reset"}}
reset_ctx = DeskContext(user_id=reset_row["customer_id"])
desk.invoke(
    {"messages": [{"role": "user", "content": reset_text}]},
    config=reset_cfg,
    context=reset_ctx,
)
parked = desk.get_state(reset_cfg)
print("reset_parked", bool(parked.interrupts))
if parked.interrupts:
    print("reset_payload", parked.interrupts[0].value)
approved = desk.invoke(
    Command(resume=APPROVE),
    config=reset_cfg,
    context=reset_ctx,
)
reset_messages = approved.get("messages") or []
print("reset_reply", content_text(reset_messages[-1]) if reset_messages else "")

vpn_row = by_id["TC-1002"]
vpn_text = (
    f"Ticket {vpn_row['ticket_id']} for employee {vpn_row['customer_id']}: "
    f"{vpn_row['text']}"
)
vpn = desk.invoke(
    {"messages": [{"role": "user", "content": vpn_text}]},
    config={"configurable": {"thread_id": "lab-5-26-vpn"}},
    context=DeskContext(user_id=vpn_row["customer_id"]),
)
vpn_messages = vpn.get("messages") or []
print("vpn_reply", content_text(vpn_messages[-1]) if vpn_messages else "")

oos_text = (
    "Ticket TC-1099 for employee E-4101: I need a new 27 inch monitor for my desk."
)
oos = desk.invoke(
    {"messages": [{"role": "user", "content": oos_text}]},
    config={"configurable": {"thread_id": "lab-5-26-oos"}},
    context=DeskContext(user_id="E-4101"),
)
oos_messages = oos.get("messages") or []
print("oos_reply", content_text(oos_messages[-1]) if oos_messages else "")
print("fixed_shape_prefix", "I cannot help with that from the IT desk:")

# %%
proc = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_techcorp_tools.py",
        "tests/test_techcorp_desk.py",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=root,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("pytest_stdout")
print(proc.stdout)
print("pytest_stderr")
print(proc.stderr)
print("exit_code", proc.returncode)
