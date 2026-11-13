# %%
"""Lab 10.3: build the three-node DataFlow triage graph.

What we build: you type the triage desk's notebook, TriageState, and the builder that wires three nodes
in a line, classify then lookup then reply, and compiles them. The three nodes are already written in
dataflow/graphs/v1_triage.py; you import them and read them. Then you print the drawing and send one real
ticket through the graph on your model.

What you learn: a StateGraph is a notebook plus boxes plus arrows. Each key of the state is optional
(total=False) because no node writes all of them; each node returns only the keys it changes; add_node
names a box, add_edge draws a fixed arrow, START and END are the doors; and compile() checks the drawing's
names, not your intent. The runtime carries the per-run envelope (DeskContext: who is asking, which model)
that is not part of the notebook; classify takes its model from the builder, else from that envelope, else
from config.

What will be true on your screen: the model line and the versions, the state's four keys, the graph's
nodes and its drawing (start, classify, lookup, reply, end), then T-3002 through the graph: the route
the model picked, the order lookup found, and the reply.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys
from typing import Any, TypedDict

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.v1_triage import classify, lookup, reply

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: TriageState and build_triage. The signature and docstring are given; you type the rest.
# The package's finished version is TriageState and build_v1_triage in dataflow/graphs/v1_triage.py.
class TriageState(TypedDict, total=False):
    """The notebook the run carries: the ticket in, the route, the order found, the reply out."""
    ticket: str
    route: str
    order: dict[str, Any]
    reply: str


def build_triage(model=None):
    """Three nodes in a line, classify then lookup then reply, compiled. model goes to classify; None: the run's context, then config."""
    builder = StateGraph(TriageState, context_schema=DeskContext)

    def classify_node(state: TriageState, runtime: Runtime[DeskContext] | None = None) -> dict:
        return classify(state, runtime=runtime, model=model)

    builder.add_node("classify", classify_node)
    builder.add_node("lookup", lookup)
    builder.add_node("reply", reply)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "lookup")
    builder.add_edge("lookup", "reply")
    builder.add_edge("reply", END)
    return builder.compile()


# BREAK: delete the line builder.add_edge("reply", END) and run. It still compiles and runs, and the drawing
# still ends at __end__: on this version a node with no way out simply ends the run, so compile checks names,
# not what you meant. Put it back. Then misspell a node in an edge, builder.add_edge("lookup", "replly"), and
# run: compile refuses with ValueError Found edge ending at unknown node `replly`. Put it back and run.

# %%
print("state_keys", list(TriageState.__annotations__))
graph = build_triage(model=chat)
print("nodes", list(graph.get_graph().nodes))
print(graph.get_graph().draw_mermaid())

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
ticket = by_id["T-3002"]["text"]
print("ticket T-3002", ticket)
state = graph.invoke({"ticket": ticket})
for key in ("route", "order", "reply"):
    print(key, state.get(key))
