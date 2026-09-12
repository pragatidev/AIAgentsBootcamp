# %% [markdown]
# Build a supervisor with two specialists.
#
# T-3005 on thread lab-15-2. Stream updates so the capture shows
# who ran. The writer parks on the refund gate. Resume with approve.

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
print("refunds_path", refunds_path.as_posix())

graph = build_v7_supervisor()
thread = {"configurable": {"thread_id": "lab-15-2"}}
payload = {"ticket": ticket["text"]}

print("cell", 1)
order = []
for update in graph.stream(payload, thread, stream_mode="updates"):
    if not isinstance(update, dict):
        print("update", update)
        continue
    print("update_nodes", list(update.keys()))
    for name in update.keys():
        if not str(name).startswith("__"):
            order.append(str(name))
            print("node", name)
print("node_order", " -> ".join(order))

state = graph.get_state(thread)
notes = list((state.values or {}).get("notes") or [])
print("notes")
for note in notes:
    print("note", note)
    if isinstance(note, dict):
        print("note_source", note.get("source"))
print("handoffs", (state.values or {}).get("handoffs"))
print("usage_tokens", (state.values or {}).get("usage_tokens"))
print("interrupts", state.interrupts)
print("next", state.next)

# %%
print("cell", 2)
if state.interrupts:
    payload_gate = state.interrupts[0].value
    print("interrupt_payload", payload_gate)
    done = graph.invoke(Command(resume="approve"), thread)
else:
    print("did_not_park")
    done = state.values or {}
print("reply", done.get("reply") if isinstance(done, dict) else done)
print("refund", done.get("refund") if isinstance(done, dict) else None)
print("handoffs", done.get("handoffs") if isinstance(done, dict) else None)
print("usage_tokens", done.get("usage_tokens") if isinstance(done, dict) else None)
print("usage_log", done.get("usage_log") if isinstance(done, dict) else None)
print("stop_reason", done.get("stop_reason") if isinstance(done, dict) else None)
rows = read_refunds()
print("refunds_rows", len(rows))
for row in rows:
    print("refund_row", row)
