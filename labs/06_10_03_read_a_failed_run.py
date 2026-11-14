# %%
"""Lab 18.3: read a failed run in a trace.

What we build: a small desk of three steps, stash (finds the order id in the ticket), check (refuses an order id the
shop does not know) and carrier (asks the carrier for the parcel), with the carrier down for good. We run it with the
package's local tracer, which writes one line per step to a trace file, and we write the function that turns "it
failed" into three answers: which node broke, what it was given, and the error.

What you learn: the tracer writes a step's line when the step ends, so the first error line in the file is where the
failure began, and every line above it in the tree (the node, the graph, the run) repeats the same error on its way
out. The trace knows where and what; the checkpoint knows the input: the thread's saved state is the state the failed
node was handed, and its next names the same node. Together they answer the question in one screen. This desk calls
no model, so the run takes under a second on any machine.

What will be true on your screen: the model line (none) and the versions, the ticket T-3002, the run failing with
CarrierTimeout, then your function's answer: the failed span is the tool fetch_carrier_status, the node is carrier,
the input is the ticket with order_id DF-1002, the error is "CarrierTimeout: carrier timeout on attempt 1 for
DF-1002", and the checkpoint's next is ('carrier',). Then the package's waterfall: the run, the graph, the carrier
node and the tool marked FAIL with the same error, check and stash with their results. The waterfall lists steps that
started in the same second longest first, so carrier sits above check and stash; the order they finished in is the
trace file's order, the one your function reads.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from dataflow.ops import tracer
from dataflow.ops.tracer import FailState, carrier_node, render_waterfall, stash_ticket, traced_invoke
from dataflow.tools.flaky import reset_flaky, set_always_fail
from dataflow.tools.orders import lookup_order_by_id

print("model none: this desk calls no model")
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# The small desk. check is the step that refuses an order the shop does not know, before the carrier is asked.
def check(state: FailState) -> dict:
    order_id = state.get("order_id") or ""
    if not lookup_order_by_id(order_id).get("found"):
        raise ValueError(f"unknown order {order_id}")
    return {}


def build_small_desk():
    builder = StateGraph(FailState)
    builder.add_node("stash", stash_ticket)
    builder.add_node("check", check)
    builder.add_node("carrier", carrier_node)
    builder.add_edge(START, "stash")
    builder.add_edge("stash", "check")
    builder.add_edge("check", "carrier")
    builder.add_edge("carrier", END)
    return builder.compile(checkpointer=InMemorySaver())


# %%
# TYPE THIS: traced_run and first_failure. The signatures and docstrings are given; you type the rest.
# The package has no failure finder; tests/test_dataflow_tracer.py::test_tool_error_span_marked checks the same FAIL
# line through the package's render_waterfall.
def traced_run(graph, ticket_text, thread_id):
    """Run the desk under the local tracer. Return the trace file and the thread config, failed or not."""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        output, trace_file = traced_invoke(graph, {"ticket": ticket_text}, config, run_name=thread_id)
        print("run_finished", output)
    except Exception as exc:
        print("run_failed", type(exc).__name__, exc)
        trace_file = tracer.last_trace_path
    return trace_file, config


def first_failure(trace_file, graph, config):
    """Where the run broke: the first error line, the node it was in, the node's input, the error."""
    spans = [json.loads(line) for line in Path(trace_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    failed = [span for span in spans if span["status"] == "error"]
    if not failed:
        print("no failure in this trace")
        return None
    first = failed[0]
    node = next(span for span in failed if span["kind"] == "chain")
    saved = graph.get_state(config)
    print("failed_span", first["kind"], first["name"])
    print("node", node["name"])
    print("input", saved.values)
    print("error", first["error"])
    print("checkpoint_next", saved.next)
    return {"node": node["name"], "input": saved.values, "error": first["error"]}


# BREAK: plant a second failure. Change the ticket line below to
# ticket_text = ticket["text"].replace("DF-1002", "DF-9999")
# and run. Your first_failure now names a different node: check, with order_id DF-9999 in the input and
# "ValueError: unknown order DF-9999"; the failed span is the chain check itself, there is no carrier line in the
# waterfall at all, because the run never got that far. Put it back and run.

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = [json.loads(line) for line in tickets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
ticket = {row["ticket_id"]: row for row in rows}["T-3002"]
ticket_text = ticket["text"]
print("ticket", ticket["ticket_id"], ticket_text)

reset_flaky()
set_always_fail(True)
graph = build_small_desk()
trace_file, config = traced_run(graph, ticket_text, "lab-18-3")
print("trace_file", Path(trace_file).name)
found = first_failure(trace_file, graph, config)

# %%
print("waterfall")
print(render_waterfall(trace_file))
reset_flaky()

# %%
# The trace file as it sits on disk: one line per step, each written when its step ended, so a step's line comes
# after the lines of the steps inside it. Read the status on each line from the top. The first line with status
# error is where the failure began (the tool); the carrier node, the graph (LangGraph) and the run come after it,
# each repeating the same error on its way out. Every line printed below is the file's line, unchanged.
print("trace_file_lines", Path(trace_file).name)
for number, line in enumerate(Path(trace_file).read_text(encoding="utf-8").splitlines(), start=1):
    print(number, line)
