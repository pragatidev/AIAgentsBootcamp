# %%
"""Lab 18.4: change a graph while threads are live.

What we build: nothing to ship. Two refund tickets (T-3001, on two threads) park on the desk from build_v4_hitl
with a SQLite saver, as if two reviewers had not answered yet on the day you deploy. Then the desk is built again
from v4_hitl's own parts, the way a deploy brings it back: first with one added state key that is not required,
priority, and every node name kept; then with the refund node renamed to refunds; then with the old name back, a
rollback. Each time a parked thread is resumed with approve, and you print its snapshot and the refund rows before
and after, and what the resume did. You type the check you run before you ship: the threads parked in the file,
each with its next, and the parked threads a change would strand.

What you learn: the file keeps each thread's values and the name of the node it waits in, never the code. A resume
runs whichever graph you built today. An added key that is not required changes nothing for a parked thread: the
resume pays, one row. A renamed node is different, and on this pin it is quiet: the resume raises no error, pays
nothing and writes no new save point; the approval is only kept as a pending write, and the renamed graph shows the
thread with next () and no interrupt, as if it had finished. Build the old name back and the same thread is parked
at refund again, and an approve pays. So the check reads the parked threads through the graph that is live today;
read through the new graph, a stranded thread does not show at all.

What will be true on your screen: the model line and the versions; both threads parked at refund with the
reviewer's question, and the parked list with next ('refund',) for each. Change 1: nothing leaving, ship True; the
resume of lab-18-4-a with no error, the refund reply, save points 3 to 4, refund rows 0 to 1, then the snapshot with
next (). Change 2: refund leaving, lab-18-4-b blocked, ship False; we ship it anyway: before the resume the renamed
graph already shows lab-18-4-b with next () and 0 interrupts; the resume raises no error, the reply is None, save
points 3 to 3, refund rows 1 to 1, pending writes ['__resume__', '__interrupt__']; the parked list through the
renamed graph is empty, through the live one it still names lab-18-4-b. The rollback: next ('refund',) and 1
interrupt again, the resume pays, rows 1 to 2, and nothing is parked.
"""

from importlib.metadata import version
from pathlib import Path
from typing import NotRequired
import json
import os
import sqlite3
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

import config
from dataflow.graphs.v4_hitl import DeskContext, HitlState, build_v4_hitl, classify
from dataflow.graphs.v4_hitl import lookup_node, pick_route, policy_node, refund_node
from dataflow.tools.refund import read_refunds

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
TICKET = by_id["T-3001"]["text"]
APPROVE = {"action": "approve", "actor": "lab-reviewer"}
# The ledger and the database are temp files for this run only.
work = Path(tempfile.mkdtemp(prefix="lab_18_4_"))
os.environ["DATAFLOW_REFUNDS_PATH"] = str(work / "refunds.jsonl")
saver = SqliteSaver(sqlite3.connect(str(work / "checkpoints.sqlite"), check_same_thread=False))


# %%
# Given: the desk built again from v4_hitl's own parts, as a deploy brings it back. The same nodes and edges as
# build_v4_hitl (v4_hitl.py lines 366 to 399), with two knobs: the state schema and the refund node's name.
class HitlStateV2(HitlState):
    priority: NotRequired[str]  # the added key: not required, so a notebook saved without it still fits


def build_desk(saver, state=HitlState, refund_name="refund"):
    def classify_node(state, runtime=None):
        return classify(state, runtime=runtime, model=chat)

    builder = StateGraph(state, context_schema=DeskContext)
    builder.add_node("classify", classify_node)
    builder.add_node("lookup", lookup_node)
    builder.add_node("policy", policy_node)
    builder.add_node(refund_name, refund_node)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify", pick_route, {"lookup": "lookup", "refund": refund_name, "policy": "policy"}
    )
    builder.add_edge("lookup", END)
    builder.add_edge("policy", END)
    builder.add_edge(refund_name, END)
    return builder.compile(checkpointer=saver)


def snapshot(graph, thread_id, label):
    """What this graph reads for one thread: the keys, next, the interrupts, the reply, and the refund rows."""
    state = graph.get_state({"configurable": {"thread_id": thread_id}})
    print(label, thread_id, "keys", sorted(state.values), "next", state.next, "interrupts", len(state.interrupts))
    print(label, thread_id, "reply", state.values.get("reply"), "refunds_rows", len(read_refunds()))


def resume(graph, saver, thread_id, decision):
    """Resume one thread and say what the resume did: the reply, save points and rows before and after, writes."""
    thread = {"configurable": {"thread_id": thread_id}}
    sql = "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?"
    points, rows = saver.conn.execute(sql, (thread_id,)).fetchone()[0], len(read_refunds())
    out = graph.invoke(Command(resume=decision), thread)
    print("resume", thread_id, "error none", "reply", out.get("reply"))
    print("resume", thread_id, "save_points", points, "to", saver.conn.execute(sql, (thread_id,)).fetchone()[0],
          "refunds_rows", rows, "to", len(read_refunds()))
    print("resume", thread_id, "pending_writes", [write[1] for write in saver.get_tuple(thread).pending_writes])


# %%
# TYPE THIS: parked_threads and blocked_by, the check before you ship. The signatures and docstrings are given.
# The package has no such check; on a deployed Agent Server the docs' version is the thread search with status
# interrupted, then get state on each thread.
def parked_threads(saver, live_graph):
    """Every thread in the file waiting on an interrupt, with the node it waits in, read through live_graph."""
    parked = {}
    for (thread_id,) in saver.conn.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id"):
        state = live_graph.get_state({"configurable": {"thread_id": thread_id}})
        if state.interrupts:
            parked[thread_id] = state.next
    return parked


def blocked_by(saver, live_graph, new_graph):
    """The node names the new graph takes away, and the parked threads whose next names one of them."""
    leaving = sorted(set(live_graph.nodes) - set(new_graph.nodes))
    parked = parked_threads(saver, live_graph)
    blocked = {thread_id: nxt for thread_id, nxt in parked.items() if set(nxt) & set(leaving)}
    print("leaving", leaving, "blocked", blocked, "ship", not blocked)
    return blocked


# BREAK: in blocked_by, change parked = parked_threads(saver, live_graph) to
# parked = parked_threads(saver, new_graph) and run. Nothing fails, and that is the danger: before change 2 the
# check now reads the parked threads through the renamed graph, which cannot see a thread waiting in refund, so it
# prints leaving ['refund'], blocked {}, ship True, and lab-18-4-b is stranded with no warning. Put it back and run.

# %%
# Yesterday's deploy: two refunds parked on build_v4_hitl, the desk from Section 14, on a SQLite saver.
live = build_v4_hitl(checkpointer=saver, model=chat)
for thread_id in ("lab-18-4-a", "lab-18-4-b"):
    parked = live.invoke({"ticket": TICKET}, {"configurable": {"thread_id": thread_id}})
    question = parked["__interrupt__"][0].value["question"] if parked.get("__interrupt__") else None
    print("ticket T-3001", thread_id, "route", parked.get("route"), "question", question)
    snapshot(live, thread_id, "parked")
print("parked_threads", parked_threads(saver, live))

# %%
# Change 1: one added key that is not required, priority. Every node keeps its name.
added_key = build_desk(saver, state=HitlStateV2)
print("change 1: added key priority")
blocked_by(saver, live, added_key)
resume(added_key, saver, "lab-18-4-a", APPROVE)
snapshot(added_key, "lab-18-4-a", "after")

# %%
# Change 2: the refund node renamed to refunds. The check says no; we ship it anyway, to see what the pin does.
renamed = build_desk(saver, state=HitlStateV2, refund_name="refunds")
print("change 2: refund renamed to refunds")
blocked_by(saver, added_key, renamed)
snapshot(renamed, "lab-18-4-b", "before")
resume(renamed, saver, "lab-18-4-b", APPROVE)
snapshot(renamed, "lab-18-4-b", "after")
print("parked_threads through renamed", parked_threads(saver, renamed))
print("parked_threads through added_key", parked_threads(saver, added_key))

# %%
# The rollback: the desk built with the old name again, on the same file.
rolled_back = build_desk(saver, state=HitlStateV2)
print("rollback: refund is back")
snapshot(rolled_back, "lab-18-4-b", "before")
resume(rolled_back, saver, "lab-18-4-b", APPROVE)
snapshot(rolled_back, "lab-18-4-b", "after")
print("parked_threads", parked_threads(saver, rolled_back))
print("refunds", [(row["order_id"], row["amount"], row["reason"]) for row in read_refunds()])
saver.conn.close()
