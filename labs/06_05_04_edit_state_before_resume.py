# %%
"""Lab 14.4: edit state before you resume.

What we build: two ways for a reviewer to change the refund amount on a parked DataFlow v4 refund. The same ticket
parks on two threads at the order's 49.0. On the first thread the reviewer's answer carries the new amount and the
reviewer's name, {"decision": "approve", "amount": 20.0, "actor": ...}. On the second, the code writes the new
amount into the parked thread's state with update_state, then sends a plain approve. Both pay 20.0. Then we read
what each thread kept.

What you learn: a pause is a place where a person can change the run, not only say yes or no. The answer way puts
the change inside the resume value, so the thread keeps the whole answer as decision, with the name in it. The
state way changes the saved state itself: update_state writes a new checkpoint marked "update", and the refund node,
which runs again from its top on resume, reads refund_amount from state and builds its payload from it. The state way
leaves a mark that something changed, but not who changed it. And an edit only matters while the thread is waiting:
once the refund is written, update_state still writes a checkpoint, and the money already paid does not move.

What will be true on your screen: the model line and the versions, then T-3001 parked twice at 49.0 from the order;
the answer way's reply "Refund issued for order DF-1001. Amount: 20.0."; the state way's line with nothing left to
run and refund_amount 20.0, and the same reply; two refund rows at 20.0; then the record: the answer thread keeps
the decision with the reviewer's name and its checkpoints are input and loop only, the state thread's decision is
the word approve, no name, with an update checkpoint among its loops.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.graphs.v4_hitl import build_v4_hitl, resume_with
from dataflow.tools.refund import get_refunds_path, read_refunds

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: edit_in_the_answer, edit_the_state and who_changed_it. The signatures and docstrings are given; you type
# the rest. The package has no version of these; tests/test_dataflow_hitl.py checks the same two edits
# (test_edit_in_answer and test_edit_before_resume).
def edit_in_the_answer(graph, thread_id, amount, actor):
    """Way one: the reviewer's answer carries the new amount and who decided."""
    config = {"configurable": {"thread_id": thread_id}}
    return resume_with(graph, config, {"decision": "approve", "amount": amount, "actor": actor})


def edit_the_state(graph, thread_id, amount):
    """Way two: write the new amount into the parked thread's state, then send a plain approve."""
    config = {"configurable": {"thread_id": thread_id}}
    graph.update_state(config, {"refund_amount": amount})
    out = resume_with(graph, config, "approve")
    state = graph.get_state(config)
    print("state_after", thread_id, "next", state.next, "refund_amount", state.values.get("refund_amount"))
    return out


def who_changed_it(graph, thread_id):
    """What the thread kept: the answer, the name in it, and where each of its checkpoints came from."""
    config = {"configurable": {"thread_id": thread_id}}
    values = graph.get_state(config).values
    print("record", thread_id, "decision", values.get("decision"), "actor", values.get("actor"))
    sources = [snapshot.metadata.get("source") for snapshot in graph.get_state_history(config)]
    print("checkpoints", thread_id, list(reversed(sources)))


# BREAK: in edit_the_state, move the line graph.update_state(config, {"refund_amount": amount}) down one line, below
# out = resume_with(graph, config, "approve"), and run. No error. The state way now pays 49.0: its reply says
# "Amount: 49.0." and its row is 49.0, while state_after says refund_amount 20.0. The edit came after the refund was
# written: it made a new checkpoint and changed nothing that was paid. Put it back and run.

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = [json.loads(line) for line in tickets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
ticket = {row["ticket_id"]: row for row in rows}["T-3001"]
print("ticket", ticket["ticket_id"], ticket["text"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
print("refunds_path", refunds_path.relative_to(root).as_posix() if refunds_path.is_relative_to(root) else refunds_path)

graph = build_v4_hitl(model=chat)
for thread_id in ("lab-14-4-answer", "lab-14-4-state"):
    config_ = {"configurable": {"thread_id": thread_id}}
    graph.invoke({"ticket": ticket["text"]}, config_)
    for item in graph.get_state(config_).interrupts:
        print("parked", thread_id, "amount", item.value["amount"], "from", item.value["amount_source"])

# %%
out = edit_in_the_answer(graph, "lab-14-4-answer", 20.0, "maria")
print("reply", out.get("reply"))
out = edit_the_state(graph, "lab-14-4-state", 20.0)
print("reply", out.get("reply"))
for row in read_refunds():
    print("refund_row", row)

# %%
who_changed_it(graph, "lab-14-4-answer")
who_changed_it(graph, "lab-14-4-state")
