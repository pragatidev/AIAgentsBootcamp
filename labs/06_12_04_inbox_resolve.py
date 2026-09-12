# %% [markdown]
# Queue interrupts into an inbox and resolve them.
#
# Cell 1 drops three tickets and lists the parked rows. Cell 2 resolves
# T-3001 with approve and T-3009 with reject, both as reviewer-anna.
# Cell 3 causes the crossed resume on purpose.

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
from dataflow.ambient.inbox import list_parked, render_inbox, resolve
from dataflow.ambient.watcher import AMBIENT_DB, watch
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.tools.refund import get_refunds_path, read_refunds

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

drop = root / "dataflow" / "data" / "inbox_drop"
drop.mkdir(parents=True, exist_ok=True)


def write_ticket(ticket_id: str, source_id: str) -> Path:
    src = by_id[source_id]
    path = drop / (ticket_id + ".json")
    path.write_text(
        json.dumps(
            {
                "ticket_id": ticket_id,
                "customer_id": src["customer_id"],
                "text": src["text"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def reset_drop() -> None:
    for leftover in drop.glob("*.json"):
        leftover.unlink()


def open_desk(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    graph = build_v4_hitl(checkpointer=saver)
    return conn, saver, graph


print("model", config.CHAT_MODEL)
db_path = Path(AMBIENT_DB)
for extra in ("", "-wal", "-shm"):
    leftover = Path(str(db_path) + extra)
    if leftover.exists():
        leftover.unlink()
refunds_path = get_refunds_path()
if refunds_path.exists():
    refunds_path.unlink()
print("sqlite", db_path.as_posix())
print("refunds_path", refunds_path.as_posix())

conn, saver, graph = open_desk(db_path)

print("cell", 1)
reset_drop()
write_ticket("T-3001", "T-3001")
write_ticket("T-3009", "T-3009")
write_ticket("T-3002", "T-3002")
watch(drop, graph, once=True)
inbox = list_parked(saver, graph)
print("inbox_rows", len(inbox))
print(render_inbox(inbox))
for row in inbox:
    print("parked_thread", row.get("thread_id"))

# %%
print("cell", 2)
approved = resolve(graph, "T-3001", "approve", actor="reviewer-anna")
print("resolve_T-3001_reply", approved.get("reply"))
print("resolve_T-3001_actor", approved.get("actor"))
print("resolve_T-3001_refund", approved.get("refund"))
rejected = resolve(graph, "T-3009", "reject", actor="reviewer-anna")
print("resolve_T-3009_reply", rejected.get("reply"))
print("resolve_T-3009_actor", rejected.get("actor"))
print("resolve_T-3009_refund", rejected.get("refund"))
print("refunds_rows")
for row in read_refunds():
    print(row)
inbox_after = list_parked(saver, graph)
print("inbox_rows_after", len(inbox_after))
print(render_inbox(inbox_after))

# %%
print("cell", 3)


def resolve_most_recent(graph, checkpointer, answer):
    """BUG: resumes whichever parked thread is newest, not the row the reviewer meant."""
    rows = list_parked(checkpointer, graph)
    newest = max(
        rows,
        key=lambda r: (str(r.get("parked_at") or ""), str(r.get("thread_id") or "")),
    )
    print("bug_picked_thread", newest.get("thread_id"))
    return resolve(graph, newest["thread_id"], answer, actor="reviewer-anna")


reset_drop()
write_ticket("T-3001-b", "T-3001")
write_ticket("T-3009-b", "T-3009")
watch(drop, graph, once=True)
crossed_inbox = list_parked(saver, graph)
print("crossed_inbox_rows", len(crossed_inbox))
print(render_inbox(crossed_inbox))
if crossed_inbox:
    intended = min(
        crossed_inbox,
        key=lambda r: (str(r.get("parked_at") or ""), str(r.get("thread_id") or "")),
    )
    print("reviewer_intended", intended.get("thread_id"))
    before_rows = list(read_refunds())
    crossed = resolve_most_recent(graph, saver, "approve")
    print("actually_resumed", crossed.get("thread_id"))
    print("crossed_reply", crossed.get("reply"))
    print("crossed_refund", crossed.get("refund"))
    after_rows = list(read_refunds())
    print("refund_rows_after_crossed")
    for row in after_rows:
        print(row)
    new_rows = after_rows[len(before_rows) :]
    print("new_refund_row", new_rows[-1] if new_rows else None)
    print("intended_equals_resumed", intended.get("thread_id") == crossed.get("thread_id"))
print("every row carries its own thread id")
