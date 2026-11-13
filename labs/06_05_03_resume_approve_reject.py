# %%
"""Lab 14.3: resume with Command: approve and reject.

What we build: the reviewer's side of the DataFlow v4 refund desk. The same refund ticket parks on two threads.
Then the reviewer's answers come back, the way they would from a review screen: a thread id and a word. One
thread is approved and one is rejected, and each answer goes in as Command(resume=...) on its own thread.

What you learn: a parked run is finished by invoking the same graph again with Command(resume=answer) and the same
thread id. The refund node starts again from its top, interrupt() returns the answer this time, and the node writes
a refund row on approve and writes nothing on reject. The thread id is the whole contract between the pause and the
answer: LangGraph does not check it against anything. An id it has never seen is a new conversation, so a typo
does not raise. It starts a fresh run with no ticket, and the approval goes nowhere.

What will be true on your screen: the model line and the versions, then T-3001 parked on lab-14-3-approve and on
lab-14-3-reject, each with the question "Approve this refund of 49.0 on order DF-1001?"; then approve: the reply
"Refund issued for order DF-1001. Amount: 49.0.", one row written, nothing left to run; then reject: "Refund
declined for order DF-1001. Reason: reviewer rejected the refund", no row written; at the end both threads with
nothing left to run and one row in the ledger.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.types import Command

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools.refund import get_refunds_path, read_refunds

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: resume_with, park and answer. The signatures and docstrings are given; you type the rest.
# The package's finished resume_with is in dataflow/graphs/v4_hitl.py (lines 345 to 347); park and answer have no
# package version, and tests/test_dataflow_hitl.py checks the same approve and reject with invoke.
def resume_with(graph, config, decision):
    """Resume a parked thread with the reviewer's answer."""
    return graph.invoke(Command(resume=decision), config)


def park(graph, text, thread_id):
    """Start the ticket on its own thread and show what the thread waits for."""
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke({"ticket": text}, config)
    state = graph.get_state(config)
    print("parked", thread_id, "next", state.next)
    for item in state.interrupts:
        print("question", item.value["question"])
    return state.next


def answer(graph, thread_id, decision):
    """The review screen sends back a thread id and an answer: resume that thread with it."""
    config = {"configurable": {"thread_id": thread_id}}
    rows_before = len(read_refunds())
    out = resume_with(graph, config, decision)
    print("answer", decision, "on", thread_id)
    print("reply", out.get("reply"))
    print("parked_again", "__interrupt__" in out)
    print("rows_written", len(read_refunds()) - rows_before)
    print("thread_next", graph.get_state(config).next)
    return out


# BREAK: in the cell below, change answer(graph, "lab-14-3-approve", "approve") to
# answer(graph, "lab-14-3-aprove", "approve") and run. Nothing raises. The answer starts a new thread with no
# ticket, no refund is written, and the final lines show lab-14-3-approve still waiting at ('refund',): the customer
# was approved and never paid. Put it back and run.

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
park(graph, ticket["text"], "lab-14-3-approve")
park(graph, ticket["text"], "lab-14-3-reject")

# %%
answer(graph, "lab-14-3-approve", "approve")
answer(graph, "lab-14-3-reject", "reject")

# %%
for thread_id in ("lab-14-3-approve", "lab-14-3-reject"):
    print("final", thread_id, "next", graph.get_state({"configurable": {"thread_id": thread_id}}).next)
print("refunds_rows", len(read_refunds()))
