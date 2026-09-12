# %% [markdown]
# Overspawn and the cap.
#
# Plant a supervisor that never settles. First run has no handoff cap
# and recursion_limit 12 as the safety net. Then cap at 3 and print
# the stop reason.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.errors import GraphRecursionError
from langgraph.types import Command

import config
from dataflow.graphs.v7_supervisor import build_v7_supervisor
from dataflow.tools.refund import get_refunds_path

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

ticket = by_id["T-3005"]
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()

print("cell", 1)
uncapped = build_v7_supervisor(plant_loop=True, max_handoffs=None)
cfg_uncap = {
    "configurable": {"thread_id": "lab-15-6-uncap"},
    "recursion_limit": 12,
}
try:
    for update in uncapped.stream(
        {"ticket": ticket["text"]},
        cfg_uncap,
        stream_mode="updates",
    ):
        if not isinstance(update, dict):
            print("update", update)
            continue
        print("update_nodes", list(update.keys()))
        if "supervise" in update:
            values = (uncapped.get_state(cfg_uncap).values or {})
            print("usage_tokens", values.get("usage_tokens"))
            print("handoffs", values.get("handoffs"))
    print("uncapped", "unexpected_success")
except GraphRecursionError as exc:
    print("exception_type", type(exc).__name__)
    print("exception_message", str(exc))

# %%
print("cell", 2)
capped = build_v7_supervisor(plant_loop=True, max_handoffs=3)
thread = {"configurable": {"thread_id": "lab-15-6-cap"}}
out = capped.invoke({"ticket": ticket["text"]}, thread)
state = capped.get_state(thread)
if state.interrupts:
    print("parked_at_writer", True)
    print("interrupt_payload", state.interrupts[0].value)
    out = capped.invoke(Command(resume="approve"), thread)
print("stop_reason", out.get("stop_reason") if isinstance(out, dict) else None)
print("reply", out.get("reply") if isinstance(out, dict) else out)
print("handoffs", out.get("handoffs") if isinstance(out, dict) else None)
print("usage_tokens", out.get("usage_tokens") if isinstance(out, dict) else None)
print("usage_log", out.get("usage_log") if isinstance(out, dict) else None)
