# %% [markdown]
# Cap a runaway graph and log why it stopped.
#
# Four brakes. Recursion limit. RemainingSteps. Node timeout. Spend cap.
# The planted loop never sets done. That is the graph misbehaving, not the model.

# %%
from pathlib import Path
import asyncio
import json
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.errors import GraphRecursionError

import config
from dataflow.graphs.runaway import (
    build_graceful,
    build_runaway,
    build_spend_capped,
    build_timeout_demo,
    run_with_cap,
)

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

print("cell", 1)
graph_a = build_runaway()
try:
    run_with_cap(graph_a, ticket["text"], recursion_limit=8)
    print("runaway", "unexpected_success")
except GraphRecursionError as exc:
    print("exception_type", type(exc).__name__)
    print("exception_message", str(exc))

# %%
print("cell", 2)
graph_b = build_graceful()
started_b = time.perf_counter()
out_b = graph_b.invoke(
    {"ticket": ticket["text"], "done": False},
    {"recursion_limit": 8},
)
print("elapsed_seconds", round(time.perf_counter() - started_b, 2))
print("steps", out_b.get("steps"))
print("done", out_b.get("done"))
print("reply", out_b.get("reply"))

# %%
print("cell", 3)
graph_c = build_timeout_demo()
started_c = time.perf_counter()
try:
    out_c = asyncio.run(graph_c.ainvoke({"ticket": ticket["text"]}))
    print("elapsed_seconds", round(time.perf_counter() - started_c, 2))
    print("timeout_returned", out_c)
    print("lookup", out_c.get("lookup") if isinstance(out_c, dict) else None)
    print("timeout_error", out_c.get("timeout_error") if isinstance(out_c, dict) else None)
    print("timeout_detail", out_c.get("timeout_detail") if isinstance(out_c, dict) else None)
except Exception as exc:
    print("elapsed_seconds", round(time.perf_counter() - started_c, 2))
    print("exception_type", type(exc).__name__)
    print("exception_message", str(exc))

# %%
print("cell", 4)
graph_d = build_spend_capped(budget_tokens=600)
started_d = time.perf_counter()
out_d = graph_d.invoke({"ticket": ticket["text"]})
print("elapsed_seconds", round(time.perf_counter() - started_d, 2))
print("usage_source", out_d.get("usage_source"))
print("spent_tokens", out_d.get("spent_tokens"))
print("call_count", out_d.get("call_count"))
print("log", out_d.get("log"))
print("stop_reason", out_d.get("reply"))
