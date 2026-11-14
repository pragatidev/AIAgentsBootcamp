# %%
"""Lab 18.2, by code: fork before refund, approve the fork, count the rows.

What we build: the fork and the edit of Lab 18.2 done in code, with no server and no browser. T-3001 parks on the desk
from build_v4_hitl and a reviewer approves it: one row in the refund ledger. Then you fork from the save point
where refund runs next, let the fork run, and answer the fork with approve. Last, you edit classify's output on
that same point, so the same ticket goes down the lookup road instead.

What you learn: a fork runs the nodes after its point again, for real. The refund node parks again with the same
question, and an approve on the fork calls issue_refund again, which appends to the same ledger: two rows for one
ticket, because the fork does not know the first approval happened. An edit written as classify (update_state with
as_node) makes the road choice again from the edited route, so the ticket takes the lookup road, which never parks
and pays nothing.

What will be true on your screen: the model line and the versions; T-3001 parked with the question and 0 rows;
approved, one row; the history, newest first; the fork point (next ('refund',)), the fork parked again with the same
question, the fork approved, and refunds_rows 2 with both rows printed. Then the edit: next ('lookup',) after the
edit, the lookup reply for DF-1001, no park, and refunds_rows still 2.
"""

from importlib.metadata import version
from pathlib import Path
import json
import os
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.types import Command

import config
from dataflow.graphs.v4_hitl import build_v4_hitl, resume_with
from dataflow.tools.refund import read_refunds

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
TICKET = by_id["T-3001"]["text"]
# The ledger is a temp file for this run only.
os.environ["DATAFLOW_REFUNDS_PATH"] = str(Path(tempfile.mkdtemp(prefix="lab_18_2_fork_")) / "refunds.jsonl")


# %%
# TYPE THIS: fork_and_answer and edit_as. The signatures and docstrings are given; you type the rest.
# The package's finished versions are test_fork_reruns_nodes_after_the_fork_point in tests/test_dataflow_stream.py
# (the fork) and resume_with in dataflow/graphs/v4_hitl.py (the answer).
def fork_and_answer(graph, thread, node, decision):
    """Run again from the point where node runs next; if it parks, answer it. Return the fork's last state."""
    history = list(graph.get_state_history(thread))
    for snap in history:
        print("  step", snap.metadata.get("step"), "next", snap.next)
    point = next(snap for snap in history if snap.next == (node,))
    print("fork_point next", point.next)
    forked = graph.invoke(None, point.config)
    if not forked.get("__interrupt__"):
        return forked
    print("fork parked", forked["__interrupt__"][0].value["question"])
    return graph.invoke(Command(resume=decision), thread)


def edit_as(graph, thread, node, as_node, values):
    """Write values onto the point where node runs next, as if as_node had written them, then run on."""
    point = next(snap for snap in graph.get_state_history(thread) if snap.next == (node,))
    edited = graph.update_state(point.config, values, as_node=as_node)
    print("after_edit next", graph.get_state(edited).next)
    return graph.invoke(None, edited)


# BREAK: in the fork cell, change fork_and_answer(desk, thread, "refund", APPROVE) to
# fork_and_answer(desk, thread, "refund", {"action": "reject", "actor": "lab-reviewer"}) and run. The fork still
# parks with the same question, the reply is "Refund declined for order DF-1001. Reason: reviewer rejected the
# refund", and refunds_rows stays 1: a declined refund writes no row. Put it back and run.

# %%
APPROVE = {"action": "approve", "actor": "lab-reviewer"}
desk = build_v4_hitl(model=chat)
thread = {"configurable": {"thread_id": "lab-18-2-fork"}}
parked = desk.invoke({"ticket": TICKET}, thread)
print("ticket T-3001 route", parked.get("route"), "parked", bool(parked.get("__interrupt__")))
if parked.get("__interrupt__"):
    print("question", parked["__interrupt__"][0].value["question"], "refunds_rows", len(read_refunds()))
    done = resume_with(desk, thread, APPROVE)
    print("approved", done.get("reply"), "refunds_rows", len(read_refunds()))
    # The fork: run again from the point where refund runs next, then answer it.
    forked = fork_and_answer(desk, thread, "refund", APPROVE)
    print("fork reply", forked.get("reply"), "refunds_rows", len(read_refunds()))
    for row in read_refunds():
        print("  row", row)
    # The edit: classify's output changed on the same point, then run on from the edit.
    edited = edit_as(desk, thread, "refund", "classify", {"route": "lookup"})
    print("edited reply", edited.get("reply"), "parked", bool(edited.get("__interrupt__")))
    print("refunds_rows", len(read_refunds()))
else:
    print("the model routed this ticket to", parked.get("route"), "so there is no refund point to fork")
