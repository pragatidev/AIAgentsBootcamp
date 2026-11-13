# %%
"""Lab 15.4: watch a full DataFlow run end to end.

What we build: one small printer, show, that turns a v2 stream of the DataFlow v4 refund desk into the lines a
support screen would show, and one function that runs the desk three times through it: a lookup ticket that goes
straight through, a refund ticket that parks for a person, and the person's approval that resumes the refund on
the same thread. Then the repo's tests/test_dataflow_stream.py runs: five tests on a fake model, not on your printer.

What you learn: one printer serves every run, because every run is the same kind of stream: updates say which
node finished and what it wrote, a parked run says so in an update named __interrupt__ that carries the question
for the person, and messages count the model's chunks while classify is talking. The thread config is the run's
address: the resume stream must carry the same thread id the refund parked on, or there is nothing to resume.

What will be true on your screen: the model line and the versions, then three runs: lookup (classify, lookup, the
order's reply), refund (classify, then parked with "Approve this refund of 49.0 on order DF-1001?", no row yet),
approve (refund wrote its keys, "Refund issued for order DF-1001. Amount: 49.0.", one row), then the package tests
passing and pytest_exit 0.
"""

from importlib.metadata import version
from pathlib import Path
import json
import subprocess
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

STREAM = {"stream_mode": ["updates", "messages"], "version": "v2"}


# %%
# TYPE THIS: show and full_run. The signatures and docstrings are given; you type the rest.
# The package's tests of the same streams are tests/test_dataflow_stream.py, run in the last cell.
def show(stream):
    """Print one v2 stream: a line per node, the parked question, the count of message chunks. Return the reply."""
    reply, chunks = None, 0
    for part in stream:
        if part["type"] == "messages":
            chunks += 1
            continue
        for node, update in part["data"].items():
            if node == "__interrupt__":
                print("parked", update[0].value["question"])
            else:
                print("node", node, "wrote", sorted(update or {}))
                reply = (update or {}).get("reply", reply)
    print("message_chunks", chunks)
    return reply


def full_run(graph, lookup_text, refund_text):
    """Three runs through show: a lookup, a refund that parks, the approval on the refund's thread."""
    refund_thread = {"configurable": {"thread_id": "lab-15-4-refund"}}
    print("run lookup")
    print("reply", show(graph.stream({"ticket": lookup_text}, {"configurable": {"thread_id": "lab-15-4-lookup"}}, **STREAM)))
    print("run refund")
    print("reply", show(graph.stream({"ticket": refund_text}, refund_thread, **STREAM)))
    print("rows_before_resume", len(read_refunds()))
    print("run approve")
    print("reply", show(graph.stream(Command(resume="approve"), refund_thread, **STREAM)))
    return refund_thread


# BREAK: in full_run's last show line, delete refund_thread, (the resume stream with no thread config) and run.
# The lookup and the refund run as before, then the resume stops on ValueError: Checkpointer requires one or more
# of the following 'configurable' keys: thread_id, checkpoint_ns, checkpoint_id. The traceback points into show, at
# for part in stream: a stream starts only when it is read. Without the thread there is no parked run to find.
# Put it back and run.

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = [json.loads(line) for line in tickets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {row["ticket_id"]: row for row in rows}
print("lookup_ticket", by_id["T-3002"]["text"])
print("refund_ticket", by_id["T-3001"]["text"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()

graph = build_v4_hitl(model=chat)
refund_thread = full_run(graph, by_id["T-3002"]["text"], by_id["T-3001"]["text"])
print("refunds_rows", len(read_refunds()))
print("thread_next", graph.get_state(refund_thread).next)

# %%
sys.stdout.flush()
result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_dataflow_stream.py", "-q"], cwd=root, check=False)
print("pytest_exit", result.returncode)
