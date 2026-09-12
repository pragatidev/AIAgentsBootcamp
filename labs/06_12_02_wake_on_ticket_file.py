# %% [markdown]
# An agent that wakes on a new ticket file.
#
# Drop two ticket json files into dataflow/data/inbox_drop/. watch(once=True)
# turns each file into an invoke on a thread whose id is the ticket id.
# The lookup finishes. The refund parks. A fresh SqliteSaver still sees it.

# %%
from pathlib import Path
import json
import sqlite3
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langgraph.checkpoint.sqlite import SqliteSaver

import config
from dataflow.ambient.watcher import AMBIENT_DB, watch
from dataflow.graphs.v4_hitl import build_v4_hitl

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

drop = root / "dataflow" / "data" / "inbox_drop"
drop.mkdir(parents=True, exist_ok=True)
for leftover in drop.glob("*.json"):
    leftover.unlink()

lookup = by_id["T-3002"]
refund = by_id["T-3001"]
(drop / "T-3002.json").write_text(
    json.dumps(
        {
            "ticket_id": lookup["ticket_id"],
            "customer_id": lookup["customer_id"],
            "text": lookup["text"],
        }
    )
    + "\n",
    encoding="utf-8",
)
(drop / "T-3001.json").write_text(
    json.dumps(
        {
            "ticket_id": refund["ticket_id"],
            "customer_id": refund["customer_id"],
            "text": refund["text"],
        }
    )
    + "\n",
    encoding="utf-8",
)

db_path = Path(AMBIENT_DB)
db_path.parent.mkdir(parents=True, exist_ok=True)
for extra in ("", "-wal", "-shm"):
    leftover = Path(str(db_path) + extra)
    if leftover.exists():
        leftover.unlink()

print("model", config.CHAT_MODEL)
print("drop", drop.as_posix())
print("sqlite", db_path.as_posix())
print("files", sorted(p.name for p in drop.glob("*.json")))

conn = sqlite3.connect(str(db_path), check_same_thread=False)
saver = SqliteSaver(conn)
saver.setup()
graph = build_v4_hitl(checkpointer=saver)

print("cell", 1)
results = watch(drop, graph, once=True)
for row in results:
    print("thread_id", row.get("thread_id"))
    print("parked", row.get("parked"))
    if row.get("parked"):
        print("payload", row.get("payload"))
    else:
        print("reply", row.get("reply"))

print("cell", 2)
conn.commit()
print("sqlite_path", db_path.as_posix())
print("sqlite_exists", db_path.is_file())
conn2 = sqlite3.connect(str(db_path), check_same_thread=False)
fresh = SqliteSaver(conn2)
fresh.setup()
fresh_graph = build_v4_hitl(checkpointer=fresh)
parked_id = None
for row in results:
    if row.get("parked"):
        parked_id = row.get("thread_id")
        break
print("parked_thread", parked_id)
if parked_id:
    snap = fresh_graph.get_state({"configurable": {"thread_id": parked_id}})
    print("next", snap.next)
    print("interrupts", bool(snap.interrupts))
    if snap.interrupts:
        print("payload", snap.interrupts[0].value)
    print("parked_thread_is_in_sqlite", bool(snap.interrupts) or bool(snap.next))
