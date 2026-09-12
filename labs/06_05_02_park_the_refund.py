# %% [markdown]
# Park the refund tool for approval.
#
# When this works, the run parks with the interrupt payload on screen
# and refunds.jsonl has no new row. The process exits while the run
# is still parked.

# %%
from pathlib import Path
import json
import re
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools.refund import get_refunds_path, read_refunds

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
orders_path = root / "dataflow" / "data" / "orders.json"
tickets = []
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    tickets.append(json.loads(line))
orders = json.loads(orders_path.read_text(encoding="utf-8"))

chosen = None
for row in tickets:
    text = row.get("text") or ""
    if "refund" not in text.lower():
        continue
    match = re.search(r"DF-\d+", text.upper())
    if not match:
        continue
    order = orders.get(match.group(0))
    if not order:
        continue
    if order.get("status") != "delivered":
        continue
    days = order.get("days_since_delivery")
    if days is None or days > 30:
        continue
    chosen = {"ticket": row, "order": order, "order_id": match.group(0)}
    break

print("model", config.CHAT_MODEL)
print("chosen", chosen["ticket"]["ticket_id"], chosen["ticket"]["text"])
print("order_id", chosen["order_id"])
print("status", chosen["order"]["status"])
print("days_since_delivery", chosen["order"]["days_since_delivery"])
print("amount", chosen["order"]["amount"])

# %%
refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
print("refunds_path", refunds_path.as_posix())

graph = build_v4_hitl()
thread = {"configurable": {"thread_id": "lab-11-2"}}
parked = graph.invoke({"ticket": chosen["ticket"]["text"]}, thread)
print("thread", "lab-11-2")
print("invoke_keys", sorted(parked.keys()) if isinstance(parked, dict) else type(parked).__name__)
state = graph.get_state(thread)
print("interrupts", state.interrupts)
if state.interrupts:
    print("payload", state.interrupts[0].value)
rows = read_refunds()
print("refunds_exists", refunds_path.exists())
print("refunds_rows", len(rows))
refunds_written = refunds_path.exists() and len(rows) > 0
print("refunds_written", refunds_written)
print("parked", bool(state.interrupts))
