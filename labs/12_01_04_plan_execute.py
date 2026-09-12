# %% [markdown]
# Plan then act on a DataFlow billing ticket.
#
# When this works, the printed plan lists the tools and the extra
# lookup is blocked. The break is an execute node that calls lookup
# when the plan never named it.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.graphs.plan_execute import build_plan_execute, execute

TICKET = "I was charged twice for order DF-1003, please check and fix"
FIXTURE_PLAN = {
    "steps": [{"tool": "retrieve", "why": "read the refund policy"}],
}

print("model", config.CHAT_MODEL)
print("ticket", TICKET)

graph = build_plan_execute()
out = graph.invoke({"ticket": TICKET})
plan = out.get("plan") or {}
steps = list(plan.get("steps") or [])
print("plan_tools", [row.get("tool") for row in steps])
print("plan")
for row in steps:
    print(row.get("tool"), row.get("why"))
print("trace")
for row in list(out.get("trace") or []):
    print(row)

# %%
print("cell", "break")
print("BREAK: planted execute runs lookup without a plan step")
planted = execute(
    {"ticket": TICKET, "plan": FIXTURE_PLAN},
    plant_unplanned_lookup=True,
)
print("planted_trace")
for row in list(planted.get("trace") or []):
    print(row)

# %%
print("cell", "fix")
print("FIX: committed execute turns that call into a miss")
fixed = execute({"ticket": TICKET, "plan": FIXTURE_PLAN})
print("fixed_trace")
for row in list(fixed.get("trace") or []):
    print(row)
blocked = [
    row
    for row in list(fixed.get("trace") or [])
    if row.get("blocked")
]
print("blocked_row", blocked[0] if blocked else None)
