# %% [markdown]
# Retry policy and error handler on a flaky carrier tool.
#
# The world is flaky here, not the model. First two carrier calls time
# out. The third succeeds. Then we force the carrier down and the
# error handler returns a typed miss so the run can still speak.

# %%
from pathlib import Path
import json
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.tools.flaky import reset_flaky, set_always_fail
import dataflow.graphs.durable as durable
from dataflow.graphs.durable import build_durable

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

ticket = by_id["T-3002"]
payload = {"ticket": ticket["text"]}
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])

reset_flaky()
durable.reset_durable()
graph = build_durable()
thread = {"configurable": {"thread_id": "lab-14-2"}}

print("cell", 1)
started = time.perf_counter()
for event in graph.stream(payload, thread, stream_mode="updates"):
    print("update", event)
elapsed = time.perf_counter() - started
state = graph.get_state(thread).values
print("log", state.get("log"))
print("carrier", state.get("carrier"))
print("reply", state.get("reply"))
print("elapsed_seconds", round(elapsed, 2))

# %%
print("cell", 2)
reset_flaky()
set_always_fail(True)
durable.reset_durable()
graph_b = build_durable()
thread_b = {"configurable": {"thread_id": "lab-14-2-b"}}
started_b = time.perf_counter()
for event in graph_b.stream(payload, thread_b, stream_mode="updates"):
    print("update", event)
elapsed_b = time.perf_counter() - started_b
state_b = graph_b.get_state(thread_b).values
print("typed_miss", state_b.get("carrier"))
print("log", state_b.get("log"))
print("reply", state_b.get("reply"))
print("elapsed_seconds", round(elapsed_b, 2))
