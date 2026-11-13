# %%
"""Lab 15.3: event streaming and a parked run.

What we build: a small driver for the DataFlow v4 refund desk that a chat screen could sit on. It opens the run
with stream_events and version="v3", the way the docs now recommend for new apps, reads the run's values step by
step, and then asks the stream one question before it says anything to the customer: did this run park? When it
parked, the driver shows the reviewer's question and stops. When the reviewer approves, the same driver opens a
second event stream with Command(resume="approve") on the same thread and reads the finished output.

What you learn: an event stream is not a list of raw events you sort through. It hands you views of the run:
values (the state after each step), messages (the model's output as it is made), and three answers a screen needs,
interrupted (did it park), interrupts (what it is waiting for, with the payload the refund node built) and output
(the state when the stream ended). output on a parked run is the state so far, not an answer: it has a route and
no reply. Only interrupted tells you which one you are holding.

What will be true on your screen: the model line and the versions, then T-3001: three value steps, interrupted
True, the refund it parked on with its order and amount, the reviewer's question, no refund row yet; then the
resume: interrupted False, the reply "Refund issued for order DF-1001. Amount: 49.0.", one refund row, and the
thread with nothing left to run.
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
# TYPE THIS: drive. The signature and docstring are given; you type the rest.
# The package has no driver; tests/test_dataflow_hitl.py checks the same park and resume with invoke.
def drive(graph, run_input, config):
    """One v3 event stream. Print each values step, then say parked (with the question) or done (with the reply)."""
    stream = graph.stream_events(run_input, config, version="v3")
    for step, values in enumerate(stream.values):
        print("value_step", step, "keys", sorted(values))
    parked = stream.interrupted
    print("interrupted", parked)
    if parked:
        for item in stream.interrupts:
            payload = item.value
            print("parked_on", payload["action"], "order", payload["order_id"], "amount", payload["amount"])
            print("question", payload["question"])
        return "parked", stream.interrupts[0].value
    out = stream.output
    print("done route", out.get("route"), "reply", out.get("reply"))
    return "done", out


# BREAK: change parked = stream.interrupted to parked = False, and run. The refund run now says interrupted False
# and "done route refund reply None": the screen would tell the customer the run is finished with no answer.
# No resume is sent, no refund row is written, and thread_next shows the thread still waiting at ('refund',).
# Put it back and run.

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
thread = {"configurable": {"thread_id": "lab-15-3"}}
status, result = drive(graph, {"ticket": ticket["text"]}, thread)
print("rows_after_first_stream", len(read_refunds()))

# %%
if status == "parked":
    print("reviewer answers approve")
    status, result = drive(graph, Command(resume="approve"), thread)
print("status", status)
print("refunds_rows", len(read_refunds()))
print("thread_next", graph.get_state(thread).next)
