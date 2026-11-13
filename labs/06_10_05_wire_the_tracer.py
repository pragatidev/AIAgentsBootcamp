# %%
"""Lab 18.5: wire the tracer into the package.

What we build: the run entry for the DataFlow v4 refund desk with the tracer wired in. One LocalTraceHandler, the
package's local tracer, goes into the run's config as a callback, on the first run that parks the refund and again on
the resume that pays it, so both halves land in one trace file. Then a short waterfall printer that reads that file
back: every span once, under its parent, in the order it was written, ok or FAIL.

What you learn: tracing is one line in the config, callbacks, and it has to be on every call that runs the graph. A
refund is two calls: the first parks at the reviewer's question, the second resumes with the answer and writes the
refund. Wire the tracer on the first only and the refund is still paid, but the trace stops at the pause, so the one
step you most need a record of, the money moving, is the one that is missing. In the trace a parked node shows as
FAIL GraphInterrupt: that is the pause, the way LangGraph stops a run to wait, not a failure. The tracer writes to a
file and never into the desk's state.

What will be true on your screen: the model line and the versions, T-3001 parking (parked True, no refund row yet),
the approval (the package prints its own actor=anon step=issue_refund line as it writes), the reply "Refund issued for
order DF-1001. Amount: 49.0.", one refund row; then the waterfall: the run,
two LangGraph spans, the first with classify (and the model call inside it) and the refund node marked FAIL
GraphInterrupt, the second with the refund node ok and its tools; the tools list ends with issue_refund; the state's
keys with no trace in them. Then the package's own tracer tests passing.
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
from dataflow.ops import tracer
from dataflow.ops.tracer import LocalTraceHandler
from dataflow.tools.refund import get_refunds_path, read_refunds

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: run_traced and waterfall. The signatures and docstrings are given; you type the rest.
# The package's finished versions: dataflow.ops.tracer.traced_invoke (one call, traced) and render_waterfall.
def run_traced(graph, ticket_text, thread_id, decision, trace_file):
    """One refund, park and resume, both halves traced into trace_file. Returns the final state."""
    handler = LocalTraceHandler(run_name=thread_id, path=trace_file)
    handler.open_run()
    run_config = {"configurable": {"thread_id": thread_id}, "callbacks": [handler]}
    first = graph.invoke({"ticket": ticket_text}, run_config)
    print("parked", "__interrupt__" in first, "rows_while_parked", len(read_refunds()))
    final = graph.invoke(Command(resume=decision), run_config)
    print("reply", final.get("reply"))
    handler.close_run()
    return final


def waterfall(trace_file):
    """Print each span once, under its parent, in the order written. Return the tool names."""
    spans = [json.loads(line) for line in Path(trace_file).read_text(encoding="utf-8").splitlines() if line.strip()]

    def show(parent_id, depth):
        for span in spans:
            if span["parent_id"] == parent_id:
                mark = "FAIL " + span["error"].split(":")[0] if span["status"] == "error" else "ok"
                print("  " * depth + span["kind"], span["name"], str(span["duration_ms"]) + "ms", mark)
                show(span["id"], depth + 1)

    show(None, 0)
    tools = [span["name"] for span in spans if span["kind"] == "tool"]
    print("tools", tools)
    return tools


# BREAK: in run_traced, change the resume line to
#     final = graph.invoke(Command(resume=decision), {"configurable": {"thread_id": thread_id}})
# and run. The reply and the refund row are the same: the refund is paid. The waterfall has one LangGraph span, the
# one that parked, and the tools list is ['search_policy']: no issue_refund anywhere, the resumed half has no trace.
# Put it back and run.

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = [json.loads(line) for line in tickets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
ticket = {row["ticket_id"]: row for row in rows}["T-3001"]
print("ticket", ticket["ticket_id"], ticket["text"])

refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
trace_file = tracer.TRACES_DIR / "lab-18-5.jsonl"
trace_file.unlink(missing_ok=True)

graph = build_v4_hitl(model=chat)
final = run_traced(graph, ticket["text"], "lab-18-5", "approve", trace_file)
print("refunds_rows", len(read_refunds()))
print("trace_file", trace_file.name)

# %%
print("waterfall")
tools = waterfall(trace_file)
print("state_keys", sorted(final))

# %%
# The package's own tracer tests. The file runs them with pytest; flush first so this lab's lines print before pytest's.
sys.stdout.flush()
result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_dataflow_tracer.py", "-q"], cwd=root, check=False)
print("pytest_exit", result.returncode)
