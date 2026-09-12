# %% [markdown]
# Read a failed run in a trace.
#
# traced_invoke around a small desk graph that calls the flaky carrier
# in always-fail mode. The waterfall marks the tool span FAIL with
# CarrierTimeout. The checkpoint rail next to it has the state.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
import dataflow.ops.tracer as tracer_mod
from dataflow.ops.tracer import (
    build_failing_carrier_graph,
    render_waterfall,
    traced_invoke,
)
from dataflow.tools.flaky import reset_flaky, set_always_fail

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

ticket = by_id["T-3002"]
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])
print("tracing_callbacks", config.tracing_callbacks())

reset_flaky()
set_always_fail(True)
graph = build_failing_carrier_graph()
thread = {"configurable": {"thread_id": "lab-16-3"}}
payload = {"ticket": ticket["text"]}

print("cell", 1)
output = None
trace_path = None
try:
    output, trace_path = traced_invoke(
        graph,
        payload,
        thread,
        run_name="failed-carrier",
    )
    print("invoke_finished")
except Exception as exc:
    print("invoke_error_type", type(exc).__name__)
    print("invoke_error", exc)
    trace_path = tracer_mod.last_trace_path

print("output", output)
print("trace_path", None if trace_path is None else Path(trace_path).as_posix())

print("waterfall")
if trace_path is not None:
    text = render_waterfall(trace_path)
    print(text)
else:
    print("no trace_path")

print("cell", 2)
print("checkpoint_rail")
try:
    history = list(graph.get_state_history(thread))
except Exception as exc:
    print("history_error", type(exc).__name__, exc)
    history = []
print("history_len", len(history))
# Oldest first so the rail reads left to right.
for snap in reversed(history):
    meta = snap.metadata or {}
    values = snap.values or {}
    print(
        "step",
        meta.get("step"),
        "next",
        snap.next,
        "ticket",
        values.get("ticket"),
        "order_id",
        values.get("order_id"),
        "carrier",
        values.get("carrier"),
    )
