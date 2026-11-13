# %%
"""Lab 17.3: a receipt survives a planted crash.

What we build: the durable desk on T-3002 on a SQLite saver: carrier_check (the flaky carrier, two timeouts
then the order), send_receipt (writes one receipt row to a file), speak. You type the receipt writer as a task,
write_receipt, and the node that calls it, send_receipt, which crashes on purpose right after the receipt is
written when the crash is planted. Then you resume the thread with invoke(None, config), the "continue after an
error" door, and count the rows. Last, the same crash with two durability modes, exit and sync.

What you learn: LangGraph saves the run between nodes, so a crashed node runs again from its first line on
resume, and any side effect written plainly inside it runs again too. A task is a unit of work whose result is
saved with the run: on resume the node runs again, but the finished task hands back its saved row instead of
writing a second one. The carrier, finished before the crash, is not called again at all. The durability mode
decides how often the run is saved: sync after every step, before the next one starts; exit only when the run
ends. An error is a way of ending, so here both modes resume to one receipt; what exit loses is the save points
in between.

What will be true on your screen: the model line and the versions, the database and receipts files; the
planted crash's message, receipts_after_crash 1, the thread waiting at send_receipt, carrier_calls 3; then the
resume: the reply, receipts_after_resume 1, carrier_calls still 3, task_remembered True; then the durability
cell: exit keeps 1 save point after the crash, sync keeps 3, and both resume to 1 receipt. With the break,
receipts_after_resume is 2 and task_remembered False: the row was written again when the node ran again.

The database is dataflow/data/checkpoints_14.sqlite unless DATAFLOW_CHECKPOINTS_PATH names another; the receipts
file is dataflow/data/receipts.jsonl unless DATAFLOW_RECEIPTS_PATH names another. The lab starts both fresh.
"""

from importlib.metadata import version
from pathlib import Path
import json
import os
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.func import task
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

import config
import dataflow.graphs.durable as durable
from dataflow.envelope import DeskContext
from dataflow.graphs.durable import (
    DurableState,
    carrier_check,
    carrier_error_handler,
    count_receipts,
    get_receipts_path,
    set_crash_after_receipt,
    speak,
)
from dataflow.tools.flaky import CarrierTimeout, call_count, reset_flaky

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
TICKET = by_id["T-3002"]["text"]
CONTEXT = DeskContext(model=chat)
DB_PATH = Path(os.environ.get("DATAFLOW_CHECKPOINTS_PATH") or root / "dataflow" / "data" / "checkpoints_14.sqlite")
print("db", DB_PATH.as_posix())
print("receipts", get_receipts_path().as_posix())


# %%
# TYPE THIS: write_receipt and send_receipt. The signatures and docstrings are given; you type the rest.
# The package's finished versions are write_receipt and send_receipt in dataflow/graphs/durable.py (lines 230 to 255).
@task
def write_receipt(ticket: str, order_id: str, status: str) -> dict:
    """Append one receipt row. As a task its result is saved with the run, so a resume gets the row back."""
    row = {"ticket": ticket, "order_id": order_id, "status": status}
    path = get_receipts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def send_receipt(state: DurableState) -> dict:
    """Write the receipt through the task, then crash on purpose when the crash is planted."""
    ticket = str(state.get("ticket") or "")
    carrier = dict(state.get("carrier") or {})
    order_id = str(carrier.get("order_id") or "")
    status = str(carrier.get("status") or carrier.get("reason") or "unknown")
    row = write_receipt(ticket, order_id, status).result()
    if durable.CRASH_AFTER_RECEIPT:
        raise RuntimeError("planted crash after the receipt task")
    return {"order": {"receipt": row}}


# BREAK: in send_receipt, change the row = ... line to row = write_receipt.func(ticket, order_id, status) (the plain
# function under the task, called directly) and run. The crash looks the same, with 1 receipt. Read the resume:
# receipts_after_resume 2 and task_remembered False. send_receipt ran again from its first line and wrote the row
# again, because nothing saved it. Put it back and run.

# %%
def build_desk(saver):
    """carrier_check with its retries, then your send_receipt, then speak, saved on the given saver."""
    builder = StateGraph(DurableState, context_schema=DeskContext)
    builder.add_node(
        "carrier_check",
        carrier_check,
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.2, backoff_factor=2.0, retry_on=CarrierTimeout),
        error_handler=carrier_error_handler,
    )
    builder.add_node("send_receipt", send_receipt)
    builder.add_node("speak", speak)
    builder.add_edge(START, "carrier_check")
    builder.add_edge("carrier_check", "send_receipt")
    builder.add_edge("send_receipt", "speak")
    builder.add_edge("speak", END)
    return builder.compile(checkpointer=saver)


def fresh_files() -> None:
    """Start with no database and no receipts, so every count below is this run's."""
    for leftover in (DB_PATH, Path(f"{DB_PATH}-wal"), Path(f"{DB_PATH}-shm"), get_receipts_path()):
        leftover.unlink(missing_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# %%
fresh_files()
reset_flaky()
durable.reset_durable()
with SqliteSaver.from_conn_string(str(DB_PATH)) as saver:
    graph = build_desk(saver)
    thread = {"configurable": {"thread_id": "lab-17-3"}}
    set_crash_after_receipt(True)
    try:
        graph.invoke({"ticket": TICKET}, thread, context=CONTEXT)
    except RuntimeError as exc:
        print("planted_crash", exc)
    after_crash = count_receipts()
    print("receipts_after_crash", after_crash, "next", graph.get_state(thread).next, "carrier_calls", call_count())
    set_crash_after_receipt(False)
    resumed = graph.invoke(None, thread, context=CONTEXT)
    print("reply", resumed["reply"])
    after_resume = count_receipts()
    print("receipts_after_resume", after_resume, "carrier_calls", call_count())
    print("task_remembered", after_crash == 1 and after_resume == 1)

# %%
# The same crash with durability="exit" and with "sync": how many save points the crash left, and the resume.
for mode in ("exit", "sync"):
    fresh_files()
    reset_flaky()
    durable.reset_durable()
    with SqliteSaver.from_conn_string(str(DB_PATH)) as saver:
        graph = build_desk(saver)
        thread = {"configurable": {"thread_id": f"lab-17-3-{mode}"}}
        set_crash_after_receipt(True)
        try:
            graph.invoke({"ticket": TICKET}, thread, context=CONTEXT, durability=mode)
        except RuntimeError:
            pass
        saved = len(list(graph.get_state_history(thread)))
        set_crash_after_receipt(False)
        graph.invoke(None, thread, context=CONTEXT, durability=mode)
        print("durability", mode, "save_points_after_crash", saved, "receipts_after_resume", count_receipts())
