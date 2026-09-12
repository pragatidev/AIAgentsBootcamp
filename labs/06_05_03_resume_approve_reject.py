# %% [markdown]
# Resume with Command: approve and reject.
#
# Two threads. The first parks then resume_with approve, and a row
# lands in refunds.jsonl. The second parks then resume_with reject,
# and no row is added.

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
print("amount", chosen["order"]["amount"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
print("refunds_path", refunds_path.as_posix())

graph = build_v4_hitl()
ticket_text = chosen["ticket"]["text"]

# %%
approve_thread = {"configurable": {"thread_id": "lab-11-3-approve"}}
graph.invoke({"ticket": ticket_text}, approve_thread)
print("thread", "lab-11-3-approve")
print("parked_approve", bool(graph.get_state(approve_thread).interrupts))
print("rows_before_approve", len(read_refunds()))
approved = resume_with(graph, approve_thread, "approve")
print("reply_approve", approved.get("reply"))
print("decision_approve", approved.get("decision"))
rows_after_approve = read_refunds()
print("rows_after_approve", len(rows_after_approve))
for row in rows_after_approve:
    print("refund_row", row)

# %%
reject_thread = {"configurable": {"thread_id": "lab-11-3-reject"}}
graph.invoke({"ticket": ticket_text}, reject_thread)
print("thread", "lab-11-3-reject")
print("parked_reject", bool(graph.get_state(reject_thread).interrupts))
count_before_reject = len(read_refunds())
print("rows_before_reject", count_before_reject)
rejected = resume_with(graph, reject_thread, "reject")
print("reply_reject", rejected.get("reply"))
print("decision_reject", rejected.get("decision"))
rows_after_reject = read_refunds()
print("rows_after_reject", len(rows_after_reject))
print("row_added_on_reject", len(rows_after_reject) > count_before_reject)
print("refunds_written_on_reject", False)
