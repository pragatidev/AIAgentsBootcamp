# %%
"""Lab 16.6: a billing subgraph with its own state.

What we build: the DataFlow desk with a billing room inside it. The room is a graph of its own (fetch_invoice,
decide_adjustment, then approve_adjustment or reply_billing) with its own notebook: ticket and reply, which it
shares with the desk, and invoice and adjustment, which are its own. You type build_desk: compile the room with
the subgraph checkpointer choice, add the whole compiled room as one node, billing, beside classify, orders and
policy, and route to it. Then two tickets: T-3012 (a missing tax line, no adjustment) and T-3005 (billed twice,
which parks inside the room for a human to approve the adjustment), resumed from the desk.

What you learn: a compiled graph added as a node shares the keys both notebooks have and keeps its own keys to
itself. An interrupt inside the room pauses the whole desk, and the desk's thread answers it. The checkpointer
choice for the room decides what the room remembers: None, the default, saves it inside this one call, so a
pause inside the room resumes where it stopped; True keeps its own history across calls on the thread; False
saves nothing inside the room, so the desk still pauses but the room has no notebook to come back to.

What will be true on your screen: the model line and the versions; the room alone on T-3012 with four keys,
then the desk on T-3012 with three (invoice and adjustment stayed inside); T-3005 streamed with subgraphs on:
classify, then billing's fetch_invoice and decide_adjustment, then the pause; the desk waiting at billing with
the question about 22.0 on DF-1010, the room's own notebook (adjustment, invoice, ticket) waiting at
approve_adjustment; the resume, where only approve_adjustment runs inside; the reply; the drawing with the room
opened. With the break, the desk still pauses with the same question, the room's notebook reads None, and the
resume runs the room again from fetch_invoice, asking the model a second time.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.billing_subgraph import DeskState, build_billing_graph, classify_desk, pick_desk
from dataflow.graphs.v2_route import orders_desk, policy_desk

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
TAX_LINE, BILLED_TWICE = by_id["T-3012"]["text"], by_id["T-3005"]["text"]
CONTEXT = DeskContext(model=chat)

# The room's checkpointer. None: saved inside one call (the default). True: its own history on the thread.
# False: nothing saved inside the room.
SUBGRAPH_CHECKPOINTER = None


# %%
# TYPE THIS: build_desk. The signature and docstring are given; you type the rest.
# The package's finished version is build_desk_with_billing in dataflow/graphs/billing_subgraph.py (lines 314 to 354).
def build_desk():
    """The desk: classify, then the billing room, orders or policy. The room is one node."""
    billing = build_billing_graph(checkpointer=SUBGRAPH_CHECKPOINTER)
    builder = StateGraph(DeskState, context_schema=DeskContext)
    builder.add_node("classify", classify_desk)
    builder.add_node("billing", billing)
    builder.add_node("orders", orders_desk)
    builder.add_node("policy", policy_desk)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        pick_desk,
        {"billing": "billing", "orders": "orders", "policy": "policy"},
    )
    builder.add_edge("billing", END)
    builder.add_edge("orders", END)
    builder.add_edge("policy", END)
    return builder.compile(checkpointer=InMemorySaver())


# BREAK: change SUBGRAPH_CHECKPOINTER = None to SUBGRAPH_CHECKPOINTER = False and run. Nothing fails, and the desk
# still pauses with the same question. Read two lines: inner_state is None (the room kept no notebook), and the
# resume lines show fetch_invoice and decide_adjustment again before approve_adjustment: the room ran again from
# its first node and asked the model a second time. Put it back and run.

# %%
# What crosses the door: the room alone, then the desk on the same ticket.
alone = build_billing_graph().invoke({"ticket": TAX_LINE}, context=CONTEXT)
print("room_alone_keys", sorted(alone))
print("room_alone invoice", alone["invoice"], "adjustment", alone["adjustment"])
desk = build_desk()
out = desk.invoke({"ticket": TAX_LINE}, {"configurable": {"thread_id": "lab-16-6-tax"}}, context=CONTEXT)
print("desk_keys", sorted(out))
print("desk route", out["route"], "reply", out.get("reply"))


# %%
def show(stream) -> None:
    """One line per node that finished: where it ran (desk, or inside the room) and its name."""
    for namespace, update in stream:
        where = namespace[0].split(":")[0] if namespace else "desk"
        for node in update:
            print("  ", where, node)


thread = {"configurable": {"thread_id": "lab-16-6"}}
print("first call, T-3005")
show(desk.stream({"ticket": BILLED_TWICE}, thread, context=CONTEXT, stream_mode="updates", subgraphs=True))
parked = desk.get_state(thread, subgraphs=True)
print("desk next", parked.next, "question", parked.interrupts[0].value["question"])
inner = parked.tasks[0].state
print("inner_state", None if inner is None else sorted(inner.values), "inner next", None if inner is None else inner.next)
print("resume with approve")
show(desk.stream(Command(resume="approve"), thread, context=CONTEXT, stream_mode="updates", subgraphs=True))
done = desk.get_state(thread)
print("desk next", done.next, "reply", done.values.get("reply"))

# %%
print(desk.get_graph(xray=True).draw_mermaid())
