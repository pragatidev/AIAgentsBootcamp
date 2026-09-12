# %% [markdown]
# A receipt task survives a planted crash.
#
# write_receipt is a @task inside send_receipt. The node then raises.
# Resume with None. The receipts file should still have one row.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.checkpoint.sqlite import SqliteSaver

import config
from dataflow.tools.flaky import reset_flaky
import dataflow.graphs.durable as durable
from dataflow.graphs.durable import (
    build_durable,
    count_receipts,
    get_receipts_path,
    set_crash_after_receipt,
)

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

ticket = by_id["T-3002"]
payload = {"ticket": ticket["text"]}
db_path = root / "dataflow" / "data" / "checkpoints_14.sqlite"
receipts_path = get_receipts_path()
thread = {"configurable": {"thread_id": "lab-14-3"}}

print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("db", db_path.as_posix())
print("receipts", receipts_path.as_posix())

reset_flaky()
durable.reset_durable()
db_path.parent.mkdir(parents=True, exist_ok=True)
for extra in ("", "-wal", "-shm"):
    leftover = Path(str(db_path) + extra)
    if leftover.exists():
        leftover.unlink()
if receipts_path.exists():
    receipts_path.unlink()

with SqliteSaver.from_conn_string(str(db_path)) as saver:
    saver.setup()
    graph = build_durable(checkpointer=saver)
    set_crash_after_receipt(True)
    try:
        graph.invoke(payload, thread)
        print("planted_crash", "unexpected_success")
    except RuntimeError as exc:
        print("planted_crash", str(exc))
    n_crash = count_receipts()
    print("receipts_after_crash", n_crash)
    set_crash_after_receipt(False)
    resumed = graph.invoke(None, thread)
    print("reply", resumed.get("reply") if isinstance(resumed, dict) else resumed)
    n_resume = count_receipts()
    print("receipts_after_resume", n_resume)
    if n_resume == 1 and n_crash == 1:
        print("task_remembered", True)
    else:
        print("task_remembered", False)
        print(
            "honest_note",
            "LangGraph re-ran the task or the row count was not 1. See the numbers above.",
        )
