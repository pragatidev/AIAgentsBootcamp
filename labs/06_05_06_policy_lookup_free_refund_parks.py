# %% [markdown]
# Policy: lookup is free, refund parks. Then the tests.
#
# A lookup ticket goes straight through. A refund ticket parks.
# Then pytest tests/test_dataflow_hitl.py runs green with no key.

# %%
from pathlib import Path
import json
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools.refund import get_refunds_path

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
orders_path = root / "dataflow" / "data" / "orders.json"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row
orders = json.loads(orders_path.read_text(encoding="utf-8"))

lookup_ticket = by_id["T-3002"]
refund_ticket = None
for row in by_id.values():
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
    refund_ticket = row
    break

print("model", config.CHAT_MODEL)
print("lookup_ticket_id", lookup_ticket["ticket_id"])
print("lookup_text", lookup_ticket["text"])
print("refund_ticket_id", refund_ticket["ticket_id"])
print("refund_text", refund_ticket["text"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()

graph = build_v4_hitl()

# %%
lookup_cfg = {"configurable": {"thread_id": "lab-11-6-lookup"}}
looked = graph.invoke({"ticket": lookup_ticket["text"]}, lookup_cfg)
lookup_state = graph.get_state(lookup_cfg)
print("thread", "lab-11-6-lookup")
print("lookup_route", looked.get("route"))
print("lookup_reply", looked.get("reply"))
print("lookup_interrupts", lookup_state.interrupts)
print("lookup_parked", bool(lookup_state.interrupts))

# %%
refund_cfg = {"configurable": {"thread_id": "lab-11-6-refund"}}
graph.invoke({"ticket": refund_ticket["text"]}, refund_cfg)
refund_state = graph.get_state(refund_cfg)
print("thread", "lab-11-6-refund")
print("refund_interrupts", refund_state.interrupts)
print("refund_parked", bool(refund_state.interrupts))
if refund_state.interrupts:
    print("payload", refund_state.interrupts[0].value)

# %%
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_dataflow_hitl.py", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", result.returncode)
