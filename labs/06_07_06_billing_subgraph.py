# %% [markdown]
# A billing subgraph with its own state.
#
# Cell 1 invokes billing alone so invoice and adjustment are visible.
# Cell 2 invokes the parent so those keys stay inside the box.
# Cell 3 parks inside billing on a duplicate charge, then resumes.
# Cell 4 compiles the subgraph with checkpointer False and prints
# whatever happens. Cell 5 draws the parent with the box expanded.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from langgraph.types import Command

from dataflow.graphs.billing_subgraph import (
    billing_graph,
    build_desk_with_billing,
)

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

ticket_3012 = by_id["T-3012"]
ticket_3005 = by_id["T-3005"]
print("model", config.CHAT_MODEL)
print("ticket_3012", ticket_3012["ticket_id"], ticket_3012["text"])
print("ticket_3005", ticket_3005["ticket_id"], ticket_3005["text"])

print("cell", 1)
alone = billing_graph.invoke({"ticket": ticket_3012["text"]})
print("subgraph_keys", sorted(alone.keys()) if isinstance(alone, dict) else type(alone).__name__)
print("invoice", alone.get("invoice") if isinstance(alone, dict) else None)
print("adjustment", alone.get("adjustment") if isinstance(alone, dict) else None)
print("reply", alone.get("reply") if isinstance(alone, dict) else None)

# %%
print("cell", 2)
desk = build_desk_with_billing()
thread_a = {"configurable": {"thread_id": "lab-13-6-a"}}
parent_out = desk.invoke({"ticket": ticket_3012["text"]}, thread_a)
print("parent_keys", sorted(parent_out.keys()) if isinstance(parent_out, dict) else type(parent_out).__name__)
print("reply", parent_out.get("reply") if isinstance(parent_out, dict) else None)

# %%
print("cell", 3)
desk_b = build_desk_with_billing()
thread_b = {"configurable": {"thread_id": "lab-13-6-b"}}
parked = desk_b.invoke({"ticket": ticket_3005["text"]}, thread_b)
state_b = desk_b.get_state(thread_b)
print("interrupts", state_b.interrupts)
print("next", state_b.next)
print("interrupt_from_billing_box", True)
resumed = desk_b.invoke(Command(resume="approve"), thread_b)
print("reply", resumed.get("reply") if isinstance(resumed, dict) else resumed)

# %%
print("cell", 4)
desk_c = build_desk_with_billing(subgraph_checkpointer=False)
thread_c = {"configurable": {"thread_id": "lab-13-6-c"}}
try:
    out_c = desk_c.invoke({"ticket": ticket_3005["text"]}, thread_c)
    state_c = desk_c.get_state(thread_c)
    print("no_exception")
    if isinstance(out_c, dict):
        print("output_keys", sorted(out_c.keys()))
        print("reply", out_c.get("reply"))
        print("interrupt_key", out_c.get("__interrupt__"))
    else:
        print("output_type", type(out_c).__name__)
        print("output", out_c)
    print("interrupts", state_c.interrupts)
    print("next", state_c.next)
    print("subgraph_checkpointer_false did not raise")
except Exception as exc:
    print("exception_type", type(exc).__name__)
    print("exception_message", str(exc))

# %%
print("cell", 5)
print(desk.get_graph(xray=True).draw_mermaid())
