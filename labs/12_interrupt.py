# %%
"""S12.2 Lookup is free. Refund parks. Resume with Command."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.types import Command

from northstar.graphs.v4_hitl import build_v4_hitl

# %%
graph = build_v4_hitl()
lookup_cfg = {"configurable": {"thread_id": "lookup-1"}}
look = graph.invoke({"ticket": "Status of order NS-1001?"}, lookup_cfg)
print("lookup_reply", look.get("reply"))
print("lookup_interrupts", bool(graph.get_state(lookup_cfg).tasks and False))

# %%
refund_cfg = {"configurable": {"thread_id": "refund-1"}}
parked = graph.invoke({"ticket": "Please refund order NS-1001"}, refund_cfg)
print("parked_keys", sorted(parked.keys()) if parked else "interrupt")
state = graph.get_state(refund_cfg)
print("has_interrupt", bool(state.interrupts))
if state.interrupts:
    print("interrupt_action", state.interrupts[0].value.get("action"))

# %%
resumed = graph.invoke(Command(resume="approve"), refund_cfg)
print("refund_decision", resumed.get("decision"))
print("refund_reply", resumed.get("reply"))
