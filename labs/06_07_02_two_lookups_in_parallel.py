# %% [markdown]
# Two lookups in one superstep, then the collision without a reducer.
#
# Walk the checkpoint history oldest first. classify is one step.
# lookup and policy_search share the next step. draft_reply joins.

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
from dataflow.graphs.v6_parallel import (
    build_v6_parallel,
    build_v6_parallel_no_reducer,
)

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

ticket = by_id["T-3001"]
payload = {"ticket": ticket["text"]}
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])

graph = build_v6_parallel()
thread = {"configurable": {"thread_id": "lab-13-2"}}

started = time.perf_counter()
out = graph.invoke(payload, thread)
elapsed = time.perf_counter() - started
print("elapsed_seconds", round(elapsed, 2))
print("results", out.get("results"))
print("reply", out.get("reply"))


def write_nodes(snap) -> list:
    meta = snap.metadata or {}
    writes = meta.get("writes", {})
    if isinstance(writes, dict):
        return [name for name in writes if not str(name).startswith("__")]
    if writes:
        return list(writes)
    return []


history = list(reversed(list(graph.get_state_history(thread))))
print("history_oldest_first", len(history))
for snap in history:
    meta = snap.metadata or {}
    step = meta.get("step")
    nodes = write_nodes(snap)
    task_names = [t.name for t in (snap.tasks or ())]
    print(
        "step",
        step,
        "writes",
        nodes,
        "next",
        list(snap.next or ()),
        "tasks",
        task_names,
    )

# %%
print("no_reducer")
try:
    build_v6_parallel_no_reducer().invoke(payload)
    print("collision", "unexpected_success")
except Exception as exc:
    print("exception_type", type(exc).__name__)
    print("exception_message", str(exc))
