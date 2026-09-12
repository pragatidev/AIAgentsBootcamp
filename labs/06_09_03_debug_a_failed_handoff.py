# %% [markdown]
# Debug a failed handoff.
#
# Plant a bad billing return (order id DF-9999), watch the desk lead
# reject it and escalate. Then turn the plant off and run the good path.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.types import Command

import config
import dataflow.graphs.v7_supervisor as v7
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
v7.PLANT_BAD_RETURN = True
print("PLANT_BAD_RETURN", v7.PLANT_BAD_RETURN)
graph_bad = build_v7_supervisor()
thread_bad = {"configurable": {"thread_id": "lab-15-3"}}
out_bad = graph_bad.invoke({"ticket": ticket["text"]}, thread_bad)
state_bad = graph_bad.get_state(thread_bad)
values_bad = out_bad if isinstance(out_bad, dict) else (state_bad.values or {})
notes_bad = list(values_bad.get("notes") or [])
print("notes")
for note in notes_bad:
    print("note", note)
billing = [n for n in notes_bad if isinstance(n, dict) and n.get("source") == "billing"]
print("bad_finding", billing[-1] if billing else None)
if billing:
    print("bad_order_id", billing[-1].get("order_id"))
rejected = [n for n in notes_bad if isinstance(n, dict) and n.get("rejected")]
print("rejected_note", rejected[-1] if rejected else None)
print("reply", values_bad.get("reply"))
print("next", state_bad.next)
print("interrupts", state_bad.interrupts)

# %%
print("cell", 2)
v7.PLANT_BAD_RETURN = False
print("PLANT_BAD_RETURN", v7.PLANT_BAD_RETURN)
graph_good = build_v7_supervisor()
thread_good = {"configurable": {"thread_id": "lab-15-3-b"}}
out_good = graph_good.invoke({"ticket": ticket["text"]}, thread_good)
state_good = graph_good.get_state(thread_good)
if state_good.interrupts:
    print("interrupt_payload", state_good.interrupts[0].value)
    out_good = graph_good.invoke(Command(resume="approve"), thread_good)
values_good = out_good if isinstance(out_good, dict) else (state_good.values or {})
print("good_reply", values_good.get("reply"))
print("good_refund", values_good.get("refund"))
print("good_notes")
for note in list(values_good.get("notes") or []):
    print("note", note)
print("refunds_rows", len(read_refunds()))
