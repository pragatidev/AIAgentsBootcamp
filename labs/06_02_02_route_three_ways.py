# %%
"""Lab 11.2: route orders, policy and escalate with a real model.

What we build: you type the router, route_after_classify, which reads the route classify wrote and names
one of three roads, and the builder that wires it with add_conditional_edges and a path map from each label
to its desk. The desks are already written in dataflow/graphs/v2_route.py; each does one job and writes
the reply. Then three real tickets take three roads on your model.

What you learn: the road a ticket takes is decided by code you can read and test, not by a prompt. The
Literal return type names every road the router can pick, the path map turns a label into a node, and the
safe default sends any label nobody expected to escalate, so no ticket can be routed nowhere. compile()
does not check what your router will return; a label missing from the path map fails only when a ticket
takes it.

What will be true on your screen: the model line and the versions, the drawing with its three dotted roads,
then for T-3002, T-3003 and T-3027 the route, the desk that ran, the key that desk wrote and the reply.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys
from typing import Literal

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

import config
from dataflow.graphs.v2_route import DeskContext, TriageState, classify, escalate_desk, orders_desk, policy_desk

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: route_after_classify and build_route. The signatures and docstrings are given; you type the rest.
# The package's finished version is pick_route and build_v2_route in dataflow/graphs/v2_route.py.
def route_after_classify(state: TriageState) -> Literal["orders", "policy", "escalate"]:
    """The label classify wrote, if it is one of the three; anything else goes to escalate."""
    route = str(state.get("route") or "")
    if route in ("orders", "policy", "escalate"):
        return route
    return "escalate"


def build_route(model=None):
    """classify, then one desk chosen by route_after_classify, each desk to END."""
    builder = StateGraph(TriageState, context_schema=DeskContext)

    def classify_node(state: TriageState, runtime: Runtime[DeskContext] | None = None) -> dict:
        return classify(state, runtime=runtime, model=model)

    builder.add_node("classify", classify_node)
    builder.add_node("orders_desk", orders_desk)
    builder.add_node("policy_desk", policy_desk)
    builder.add_node("escalate_desk", escalate_desk)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {"orders": "orders_desk", "policy": "policy_desk", "escalate": "escalate_desk"},
    )
    builder.add_edge("orders_desk", END)
    builder.add_edge("policy_desk", END)
    builder.add_edge("escalate_desk", END)
    return builder.compile()


# BREAK: in route_after_classify change the line `        return route` to `        return "billing"` and run.
# It compiles, and the first ticket fails with KeyError: 'billing': the router named a road the path map does
# not have. That is the safe default's job: never return a label you did not map. Put it back and run.

# %%
graph = build_route(model=chat)
print(graph.get_graph().draw_mermaid())

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
DESK_KEY = {"orders_desk": "order", "policy_desk": "policy", "escalate_desk": "escalation"}
for ticket_id in ("T-3002", "T-3003", "T-3027"):
    print("ticket", ticket_id, by_id[ticket_id]["text"])
    for update in graph.stream({"ticket": by_id[ticket_id]["text"]}, stream_mode="updates"):
        for node, written in update.items():
            if node == "classify":
                print("route", written["route"])
            else:
                print("desk", node, "wrote", DESK_KEY[node], json.dumps(written[DESK_KEY[node]]))
                print("reply", written["reply"])
