# %% [markdown]
# Portfolio: DataFlow desk v8 with a nightly triage.
#
# Pick the date with the most tickets, run the local scheduler with
# run_now=True, print the report and the inbox. The hosted Agent Server
# cron call is shown as code and is not executed.

# %%
from pathlib import Path
from collections import Counter
import json
import sqlite3
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.checkpoint.sqlite import SqliteSaver

import config
from dataflow.ambient.inbox import list_parked, render_inbox
from dataflow.ambient.watcher import AMBIENT_DB
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.graphs.v8_nightly import run_nightly, schedule_local
from dataflow.tools.refund import get_refunds_path

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
tickets = []
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    tickets.append(json.loads(line))

counts = Counter()
for row in tickets:
    created = str(row.get("created_at") or "")
    day = created.split("T", 1)[0] if "T" in created else created[:10]
    counts[day] += 1
max_n = max(counts.values()) if counts else 0
candidates = sorted(d for d, n in counts.items() if n == max_n)
chosen = candidates[0] if candidates else ""
for day in candidates:
    texts = [
        str(r.get("text") or "")
        for r in tickets
        if (str(r.get("created_at") or "").split("T", 1)[0] if "T" in str(r.get("created_at") or "") else str(r.get("created_at") or "")[:10])
        == day
    ]
    if any("refund" in t.lower() for t in texts):
        chosen = day
        break

print("model", config.CHAT_MODEL)
print("date_counts", dict(sorted(counts.items())))
print("max_tickets", max_n)
print("date", chosen)
print("tie_break", "prefer a date that has a refund ticket so the inbox has a row")

db_path = Path(AMBIENT_DB)
db_path.parent.mkdir(parents=True, exist_ok=True)
for extra in ("", "-wal", "-shm"):
    leftover = Path(str(db_path) + extra)
    if leftover.exists():
        leftover.unlink()
refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()

conn = sqlite3.connect(str(db_path), check_same_thread=False)
saver = SqliteSaver(conn)
saver.setup()

print("cell", 1)


def _run():
    return run_nightly(chosen, checkpointer=saver)


out = schedule_local(2, 0, _run, run_now=True)
print("nightly_thread", out.get("thread_id"))
print("load_mode", out.get("load_mode"))
print("parked", out.get("parked"))
report_path = out.get("report_path")
print("report_path", report_path)
print("report_file")
if report_path and Path(report_path).is_file():
    print(Path(report_path).read_text(encoding="utf-8"), end="")
else:
    print("(missing)")

print("cell", 2)
desk = build_v4_hitl(checkpointer=saver)
inbox = list_parked(saver, desk)
print("inbox_rows", len(inbox))
print(render_inbox(inbox))

print("cell", 3)
HOSTED_CRON = (
    "from langgraph_sdk import get_client\n"
    "client = get_client(url='https://your-deployment.us.langgraph.app')\n"
    "client.crons.create(\n"
    "    assistant_id='desk',\n"
    "    schedule='0 2 * * *',\n"
    "    input={'date': '" + chosen + "'},\n"
    ")\n"
)
print("hosted_cron_not_run")
print("needs a LangSmith Deployment; this call was not executed")
print("hosted_cron_code")
print(HOSTED_CRON, end="")

print("cell", 4)
pytest_result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_dataflow_ambient.py", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", pytest_result.returncode)
