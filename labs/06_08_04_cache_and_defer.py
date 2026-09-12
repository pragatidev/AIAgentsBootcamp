# %% [markdown]
# Cache the policy node; defer the aggregator.
#
# Cell 1 runs the same return-window ticket twice on two threads, then
# once more after the short ttl. POLICY_CALLS shows whether the body ran.
# Cell 2 fans three items of different lengths, with defer off then on.

# %%
from pathlib import Path
import json
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.cache.memory import InMemoryCache

import config
from dataflow.tools.flaky import reset_flaky
import dataflow.graphs.durable as durable
from dataflow.graphs.durable import build_durable, build_two_length_fan

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

ticket = by_id["T-3003"]
payload = {"ticket": ticket["text"]}
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])

print("cell", 1)
reset_flaky()
durable.reset_durable()
cache = InMemoryCache()
# ttl must outlast one full ticket. speak on qwen3:8b is several seconds,
# so a 3 second ttl expires before the second thread starts.
graph = build_durable(cache=cache, cache_ttl=20)

started_1 = time.perf_counter()
out_1 = graph.invoke(payload, {"configurable": {"thread_id": "lab-14-4-a"}})
elapsed_1 = time.perf_counter() - started_1
print("POLICY_CALLS", durable.POLICY_CALLS)
print("elapsed_seconds", round(elapsed_1, 2))
print("reply", out_1.get("reply"))

started_2 = time.perf_counter()
out_2 = graph.invoke(payload, {"configurable": {"thread_id": "lab-14-4-b"}})
elapsed_2 = time.perf_counter() - started_2
print("POLICY_CALLS", durable.POLICY_CALLS)
print("elapsed_seconds", round(elapsed_2, 2))
print("reply", out_2.get("reply"))

print("sleep_past_ttl", 22)
time.sleep(22)
started_3 = time.perf_counter()
out_3 = graph.invoke(payload, {"configurable": {"thread_id": "lab-14-4-c"}})
elapsed_3 = time.perf_counter() - started_3
print("POLICY_CALLS", durable.POLICY_CALLS)
print("elapsed_seconds", round(elapsed_3, 2))
print("reply", out_3.get("reply"))

# %%
print("cell", 2)
off = build_two_length_fan(defer=False).invoke({})
print("summarize_runs_defer_false", len(off.get("runs") or []))
print("summarize_runs_list_defer_false", off.get("runs"))
on = build_two_length_fan(defer=True).invoke({})
print("summarize_runs_defer_true", len(on.get("runs") or []))
print("summarize_runs_list_defer_true", on.get("runs"))
