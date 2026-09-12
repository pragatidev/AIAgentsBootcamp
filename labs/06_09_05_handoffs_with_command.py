# %% [markdown]
# Handoffs with Command on a shared thread.
#
# Cell 1 walks checkpoint history on lab-15-5, oldest first, then resumes
# on the same thread. Cell 2 plants parallel writers and reads the collision.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.errors import InvalidUpdateError
from langgraph.types import Command

import config
from dataflow.graphs.v7_supervisor import build_v7_supervisor
from dataflow.tools.refund import get_refunds_path, read_refunds

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
graph = build_v7_supervisor()
thread = {"configurable": {"thread_id": "lab-15-5"}}
graph.invoke({"ticket": ticket["text"]}, thread)
state = graph.get_state(thread)
print("thread", "lab-15-5")
print("next", state.next)
print("interrupts", state.interrupts)
if state.interrupts:
    payload_gate = state.interrupts[0].value
    print("interrupt_payload", payload_gate)
notes = list((state.values or {}).get("notes") or [])
billing = [n for n in notes if isinstance(n, dict) and n.get("source") == "billing"]
print("billing_finding", billing[-1] if billing else None)
if state.interrupts and billing:
    payload_gate = state.interrupts[0].value
    finding = billing[-1]
    print("payload_order_id", payload_gate.get("order_id"))
    print("payload_amount", payload_gate.get("amount"))
    print("finding_order_id", finding.get("order_id"))
    print("finding_amount", finding.get("amount"))
    print(
        "billing_finding_travelled",
        payload_gate.get("order_id") == finding.get("order_id")
        and payload_gate.get("amount") == finding.get("amount"),
    )

print("history oldest first")
history = list(reversed(list(graph.get_state_history(thread))))
for i, snap in enumerate(history):
    meta = snap.metadata or {}
    print(
        "step",
        meta.get("step", i),
        "next",
        snap.next,
        "handoffs",
        (snap.values or {}).get("handoffs"),
    )

if state.interrupts:
    done = graph.invoke(Command(resume="approve"), thread)
    print("same_thread", True)
    print("reply", done.get("reply") if isinstance(done, dict) else done)
    print("refund", done.get("refund") if isinstance(done, dict) else None)
else:
    print("did_not_park")
    print("reply", (state.values or {}).get("reply"))

print("refunds_rows", len(read_refunds()))

# %%
print("cell", 2)
broken = build_v7_supervisor(parallel_writers=True)
try:
    broken.invoke(
        {"ticket": ticket["text"]},
        {"configurable": {"thread_id": "lab-15-5-break"}},
    )
    print("collision", "unexpected_success")
except InvalidUpdateError as exc:
    print("exception_type", type(exc).__name__)
    print("exception_message", str(exc))
print("the single writer build has no such path")
