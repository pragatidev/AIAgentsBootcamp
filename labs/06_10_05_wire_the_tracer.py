# %% [markdown]
# Wire the tracer into the package.
#
# config.tracing_callbacks() is always on. A normal lookup ticket goes
# through traced_invoke. Print the path and the first 8 waterfall
# lines, then pytest tests/test_dataflow_tracer.py.

# %%
from pathlib import Path
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.ops.tracer import render_waterfall, traced_invoke

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
print("tracing_callbacks_types", [type(cb).__name__ for cb in config.tracing_callbacks()])

graph = build_v4_hitl()
thread = {
    "configurable": {"thread_id": "lab-16-5"},
    "callbacks": config.tracing_callbacks(),
}
print("cell", 1)
output, trace_path = traced_invoke(
    graph,
    {"ticket": ticket["text"]},
    thread,
    run_name="desk-lookup",
)
print("route", output.get("route") if isinstance(output, dict) else None)
print("reply", output.get("reply") if isinstance(output, dict) else output)
print("trace_path", Path(trace_path).as_posix())

waterfall = render_waterfall(trace_path)
print("waterfall_first_8")
for i, line in enumerate(waterfall.splitlines()[:8]):
    print(line)
print("waterfall_line_count", len(waterfall.splitlines()))

print("cell", 2)
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_dataflow_tracer.py", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", result.returncode)
