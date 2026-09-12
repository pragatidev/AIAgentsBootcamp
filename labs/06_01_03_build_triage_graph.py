# %% [markdown]
# Build the three-node DataFlow triage graph.
#
# When this works, compile succeeds and the mermaid drawing names
# `__start__`, classify, lookup, reply, and `__end__`. Classify calls
# the model from config. Lookup is plain Python over orders.json.
# Reply writes one sentence, or an honest miss.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.graph import END, START, StateGraph

from dataflow.graphs.v1_triage import (
    DeskContext,
    TriageState,
    build_v1_triage,
    classify,
    lookup,
    reply,
)

print("state keys", sorted(TriageState.__annotations__))

# %%
builder = StateGraph(TriageState, context_schema=DeskContext)
builder.add_node("classify", classify)
builder.add_node("lookup", lookup)
builder.add_node("reply", reply)
builder.add_edge(START, "classify")
builder.add_edge("classify", "lookup")
builder.add_edge("lookup", "reply")
builder.add_edge("reply", END)

# %%
graph = builder.compile()
print("mermaid")
print(graph.get_graph().draw_mermaid())

# %%
packaged = build_v1_triage()
print("compiled", type(packaged).__name__)
print("nodes", sorted(packaged.get_graph().nodes))
print("package mermaid")
print(packaged.get_graph().draw_mermaid())
