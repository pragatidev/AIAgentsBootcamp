# %%
"""Lab 9.1: where the desk runs out of road.

What we build: nothing new. You run three DataFlow tickets through the Section 8 knowledge desk (the
create_agent desk with lookup_order and retrieve, built by build_rag_desk): an order (T-3002), a policy
question (T-3003) and the refund T-3001. For each you print the road the run took, node by node, and the
tools the model called. Then you print the drawing of the finished DataFlow graph desk, the one this part
builds.

What you learn: on the create_agent desk every ticket walks the same loop, the model node, the tools node,
back to the model, and only the tool the model picked differs. Nothing in that loop is a road of its own
for a refund: money would move because a model chose a tool. On the graph desk the decision is a node you
can test, each kind of ticket has a named road, and the refund road is a box you can point at.

What will be true on your screen: the model line and the versions; the desk's nodes; for each ticket its
road, the tools it called with their arguments, and the reply; whether every ticket walked the same nodes;
whether this desk has a node with refund in its name; then the graph desk's drawing and the same question
asked of it.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.rag.desk import build_rag_desk

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}

# %%
# The Section 8 desk: create_agent, the order lookup and the retrieve tool, the tool call limit.
desk = build_rag_desk(model=chat)
print("desk_nodes", list(desk.get_graph().nodes))


def content_text(content) -> str:
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in content).strip()
    return str(content or "").strip()


def walk(ticket_id: str) -> list[str]:
    """Stream one ticket in updates mode: one update per node that ran. Returns the road."""
    road: list[str] = []
    calls: list[str] = []
    reply = ""
    for update in desk.stream({"messages": [HumanMessage(content=by_id[ticket_id]["text"])]}, stream_mode="updates"):
        for node, payload in update.items():
            road.append(node)
            for message in (payload or {}).get("messages", []):
                for call in getattr(message, "tool_calls", None) or []:
                    calls.append(f"{call['name']} {json.dumps(call['args'])}")
                if message.type == "ai" and content_text(message.content):
                    reply = content_text(message.content)
    print("ticket", ticket_id, by_id[ticket_id]["text"])
    print("road", " -> ".join(road))
    print("tools_called", calls)
    print("reply", reply[:300])
    return road


roads = {ticket_id: walk(ticket_id) for ticket_id in ("T-3002", "T-3003", "T-3001")}
print("same_nodes_for_every_ticket", len({tuple(sorted(set(road))) for road in roads.values()}) == 1)
print("refund_node_on_this_desk", any("refund" in name for name in desk.get_graph().nodes))

# %%
# The graph desk this part builds: classify first, three named roads, the refund road its own node.
graph_desk = build_v4_hitl(model=chat)
print(graph_desk.get_graph().draw_mermaid())
print("refund_node_on_the_graph_desk", any("refund" in name for name in graph_desk.get_graph().nodes))
