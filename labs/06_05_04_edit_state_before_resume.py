# %% [markdown]
# Edit the state before you resume.
#
# Park a refund, print the payload amount from the order, then
# update_state with a lower refund_amount and resume with approve.
# The written row shows the edited figure.

# %%
from pathlib import Path
import json
import re
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.v4_hitl import build_v4_hitl, resume_with
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
print("order_amount", chosen["order"]["amount"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
print("refunds_path", refunds_path.as_posix())

graph = build_v4_hitl()
thread = {"configurable": {"thread_id": "lab-11-4"}}

# %%
graph.invoke({"ticket": chosen["ticket"]["text"]}, thread)
state = graph.get_state(thread)
print("thread", "lab-11-4")
print("interrupts", state.interrupts)
payload = state.interrupts[0].value
print("payload", payload)
print("payload_amount", payload["amount"])
# The node re-runs from its top on resume, which is why the edited state
# is read before the new payload is built.
graph.update_state(thread, {"refund_amount": 20.0})
print("refund_amount", graph.get_state(thread).values.get("refund_amount"))
out = resume_with(graph, thread, "approve")
print("reply", out.get("reply"))
print("decision_out", out.get("decision"))
rows = read_refunds()
print("refunds_rows", len(rows))
for row in rows:
    print("refund_row", row)
    print("written_amount", row.get("amount"))
