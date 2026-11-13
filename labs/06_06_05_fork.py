# %%
"""Lab 13.5: fork a checkpoint and continue differently.

What we build: you type fork_before, which walks a thread's saved history, picks the save point where a node is
about to run, writes a different finding onto it with update_state (which makes a new save point and touches
no old one) and runs on from the new point with invoke(None, fork_config); and original_trail_intact, which
reads every old save point back and checks it is exactly what it was. T-3001 runs on the memory desk; then you
fork before speak with an edited finding, so speak runs again on the fork. A second cell replays the refund
desk from the save point before its refund node, after a reviewer already approved the refund.

What you learn: history is a rail of save points, newest first, each with its values, the node it runs next
and its own config. A fork is a branch off that rail, never a rollback: the original points stay, and the
thread's newest point is now the fork's tip. A replay runs the nodes after the point again for real: speak
calls the model again, and on the refund desk the pause fires again, so the replay parks instead of paying a
second time. Fork from the point after a node and that node never runs again.

What will be true on your screen: the model line and the versions; the original reply; the history, newest
first, with each step, its next node and its id; the point forked from (next ('speak',)) and the new point;
the fork's reply, written by the model from the edited finding; history grown, the newest point the fork's
tip, and original_trail_intact True. Then the refund desk: parked, approved with one ledger row, the replay
parked again with the same question, still one row.
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

import config
from dataflow.graphs.v3_memory import build_v3_memory
from dataflow.graphs.v4_hitl import build_v4_hitl, resume_with
from dataflow.tools.refund import read_refunds

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
TICKET = by_id["T-3001"]["text"]


# %%
# TYPE THIS: fork_before and original_trail_intact. The signatures and docstrings are given; you type the rest.
# The package's finished version is test_fork_keeps_original_history and test_fork_reruns_nodes_after_the_fork_point
# in tests/test_dataflow_stream.py.
def fork_before(graph, thread: dict, node: str, values: dict) -> tuple:
    """Walk the history, take the point where node runs next, write values onto it, run on from the new point."""
    history = list(graph.get_state_history(thread))
    for snapshot in history:
        step, next_nodes = snapshot.metadata.get("step"), snapshot.next
        print("  step", step, "next", next_nodes, "id", snapshot.config["configurable"]["checkpoint_id"])
    before = next(snapshot for snapshot in history if snapshot.next == (node,))
    fork_config = graph.update_state(before.config, values=values)
    print("forked_from", before.config["configurable"]["checkpoint_id"], "next", before.next)
    print("fork_point", fork_config["configurable"]["checkpoint_id"])
    return history, graph.invoke(None, fork_config)


def original_trail_intact(graph, history: list) -> bool:
    """Read every old save point back by its own config: same values, same next node, as before the fork."""
    for snapshot in history:
        again = graph.get_state(snapshot.config)
        if again.values != snapshot.values or again.next != snapshot.next:
            return False
    return True


# BREAK: in fork_before, change the before = ... line to before = history[0] (the newest point, after speak) and
# run. Nothing fails. The edited finding is written onto a finished run, so next is () and nothing runs: the
# fork's reply is your edited sentence itself, not a model answer, and speak never ran on the fork. A fork has to
# start before the node you want to run again. Put it back and run.

# %%
desk = build_v3_memory(model=chat)
thread = {"configurable": {"thread_id": "lab-13-5"}}
first = desk.invoke({"ticket": TICKET}, thread)
print("ticket T-3001", TICKET)
print("route", first.get("route"))
print("original_reply", first.get("reply"))

edited = "The return window is 30 days and the lamp qualifies."
history, forked = fork_before(desk, thread, "speak", {"reply": edited})
print("edited_finding", edited)
print("fork_reply", forked.get("reply"))

# %%
after = list(desk.get_state_history(thread))
print("history_before", len(history), "history_after", len(after))
print("newest_is_fork_tip", desk.get_state(thread).values.get("reply") == forked.get("reply"))
print("original_reply_still_on_its_point", desk.get_state(history[0].config).values.get("reply") == first.get("reply"))
print("original_trail_intact", original_trail_intact(desk, history))

# %%
# A replay runs the nodes after the point for real. On the refund desk, after the approval, replay from the point
# before refund: the docs say the pause fires again. The ledger is a temp file for this run only.
os.environ["DATAFLOW_REFUNDS_PATH"] = str(Path(tempfile.mkdtemp(prefix="lab_13_5_")) / "refunds.jsonl")
refund_desk = build_v4_hitl(model=chat)
refund_thread = {"configurable": {"thread_id": "lab-13-5-refund"}}
parked = refund_desk.invoke({"ticket": TICKET}, refund_thread)
print("refund route", parked.get("route"), "parked", bool(parked.get("__interrupt__")))
if parked.get("__interrupt__"):
    print("question", parked["__interrupt__"][0].value["question"])
    done = resume_with(refund_desk, refund_thread, {"action": "approve", "actor": "lab-reviewer"})
    print("approved", done.get("reply"), "rows", len(read_refunds()))
    before_refund = next(s for s in refund_desk.get_state_history(refund_thread) if s.next == ("refund",))
    replay = refund_desk.invoke(None, before_refund.config)
    print("replay parked", bool(replay.get("__interrupt__")), "reply", replay.get("reply"))
    if replay.get("__interrupt__"):
        print("replay question", replay["__interrupt__"][0].value["question"])
    print("rows_after_replay", len(read_refunds()))
    print("thread next", refund_desk.get_state(refund_thread).next)
else:
    print("the model routed this ticket to", parked.get("route"), "so there is no refund point to replay")
