# %%
"""Lab 11.6: route with Command, and when to pick it over an edge.

What we build: you type classify_command, a node that classifies the ticket and then routes and writes in
one return, Command(goto=..., update=...), and the builder that adds it with no conditional edge at all.
Its return type, Command[Literal["orders_desk", "policy_desk", "escalate_desk"]], names the roads. Then the
same ticket goes through the edge build from lab 11.2 (build_v2_route) and through yours, and the two
drawings print one after the other.

What you learn: Command is the other way to route. goto names the next node, update writes the state, both
in the node's one return. Pick a conditional edge when the routing rule is separate from the work; pick
Command when the node that does the work also knows where to go next. The roads a Command can take are not
edges you drew, so you declare them, in the return type or with destinations= on add_node, and that
declaration is what the drawing reads. The model reaches classify through the run's context here.

What will be true on your screen: the model line and the versions, then T-3002 through both builds with
the route and the reply each gave and whether they agree, then the edge build's drawing and your Command
build's drawing, each with three dotted roads out of classify.
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
from langgraph.types import Command

import config
from dataflow.graphs.v2_route import DeskContext, TriageState, build_v2_route, classify, escalate_desk, orders_desk, policy_desk

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

ROUTE_TO_DESK = {"orders": "orders_desk", "policy": "policy_desk", "escalate": "escalate_desk"}


# %%
# TYPE THIS: classify_command and build_command. The signatures and docstrings are given; you type the rest.
# The package's finished version is classify_command and build_v2_command in dataflow/graphs/v2_command.py,
# which declares the roads with destinations= on add_node instead of in the return type.
def classify_command(
    state: TriageState, runtime: Runtime[DeskContext] | None = None
) -> Command[Literal["orders_desk", "policy_desk", "escalate_desk"]]:
    """Classify, then route and write in one return: goto is the next node, update writes the route."""
    decision = classify(state, runtime=runtime)
    route = str(decision.get("route") or "escalate")
    return Command(goto=ROUTE_TO_DESK.get(route, "escalate_desk"), update={"route": route})


def build_command():
    """classify_command, then whichever desk it named, each desk to END. No conditional edge."""
    builder = StateGraph(TriageState, context_schema=DeskContext)
    builder.add_node("classify", classify_command)
    builder.add_node("orders_desk", orders_desk)
    builder.add_node("policy_desk", policy_desk)
    builder.add_node("escalate_desk", escalate_desk)
    builder.add_edge(START, "classify")
    builder.add_edge("orders_desk", END)
    builder.add_edge("policy_desk", END)
    builder.add_edge("escalate_desk", END)
    return builder.compile()


# BREAK: change the return type of classify_command to plain -> Command (no Literal) and run. Read both: the
# ticket still reaches the same desk, but your drawing loses the three roads and shows classify going
# straight to __end__, with the desks standing alone. The roads were never edges; the declaration was the
# only thing that drew them. Put it back and run.

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
ticket = {"ticket": by_id["T-3002"]["text"]}
print("ticket T-3002", ticket["ticket"])
edge_graph = build_v2_route(model=chat)
command_graph = build_command()
edge_state = edge_graph.invoke(ticket)
command_state = command_graph.invoke(ticket, context=DeskContext(model=chat))
print("edge_route", edge_state["route"], "edge_reply", edge_state["reply"])
print("command_route", command_state["route"], "command_reply", command_state["reply"])
print("same_road", edge_state["route"] == command_state["route"] and edge_state["reply"] == command_state["reply"])

# %%
print("edge_drawing")
print(edge_graph.get_graph().draw_mermaid())
print("command_drawing")
print(command_graph.get_graph().draw_mermaid())
