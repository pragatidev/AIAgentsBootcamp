# %%
"""Lab 13.2: SQLite checkpointer, kill the process and resume.

What we build: first, run with no flag, the memory desk (build_v3_memory) on an in-memory saver: T-3001, then
the same customer's follow-up T-3028 on the same thread, which continues it, and T-3028 again on a fresh
thread, which does not. Then you type the two entry points that make a thread outlive its process. start
opens a SQLite saver on a file, runs turn one and dies on the spot with no clean shutdown, as a killed
process would. resume, run as a second process, opens a new saver on the same file, reads the notebook turn
one left, counts the thread's rows in the file with one SQL query, and runs turn two.

What you learn: the checkpointer saves the notebook after every step under the thread id, and a SQLite saver
writes each save to disk as it happens, so nothing waits for a clean exit. The thread id is the key to all of
it: the second process knows turn one only because it asks for the same thread. In memory, the thread lives as
long as the process; on a file, it lives as long as the file. This is the rubric's survive-a-kill probe, built
by you.

What will be true on your screen: no flag: the model line and the versions, turn one's reply and checkpoint
count, turn two's reply with turns 2 and a higher count, the fresh thread with turns 1. --start: the file,
the process id, turn one's reply, the checkpoint count, then "dies now" and nothing after. --resume: a
different process id, the saved notebook (turns 1 and turn one's reply), the thread's rows in the file, then
turn two with turns 2. With the break, resume finds no notebook, 0 rows, and turn two runs with turns 1:
no memory of turn one, though the reply may still read fine.

The file is dataflow/data/checkpoints.sqlite unless DATAFLOW_CHECKPOINTS_PATH names another one.
"""

from importlib.metadata import version
from pathlib import Path
import json
import os
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.v3_memory import build_v3_memory

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
TURN_ONE, TURN_TWO = by_id["T-3001"]["text"], by_id["T-3028"]["text"]
CONTEXT = DeskContext(customer_id=by_id["T-3001"]["customer_id"])
DB_PATH = Path(os.environ.get("DATAFLOW_CHECKPOINTS_PATH") or root / "dataflow" / "data" / "checkpoints.sqlite")
FLAG = next((arg for arg in sys.argv[1:] if arg in ("--start", "--resume")), "")


def turn(text: str) -> dict:
    """One ticket as the desk's input: the ticket line and the customer's message."""
    return {"ticket": text, "messages": [HumanMessage(content=text)]}


# %%
# The in-memory run: a thread in memory. Runs when no flag is given.
if not FLAG:
    desk = build_v3_memory(checkpointer=InMemorySaver(), model=chat)
    same = {"configurable": {"thread_id": "lab-13-2-memory"}}
    first = desk.invoke(turn(TURN_ONE), same, context=CONTEXT)
    print("memory turn 1 turns", first["turns"], "checkpoints", len(list(desk.get_state_history(same))))
    print("memory turn 1 reply", first["reply"])
    second = desk.invoke(turn(TURN_TWO), same, context=CONTEXT)
    print("memory turn 2 turns", second["turns"], "checkpoints", len(list(desk.get_state_history(same))))
    print("memory turn 2 reply", second["reply"])
    fresh = desk.invoke(turn(TURN_TWO), {"configurable": {"thread_id": "lab-13-2-fresh"}}, context=CONTEXT)
    print("fresh thread turns", fresh["turns"], "reply", fresh["reply"])


# %%
# TYPE THIS: THREAD, start and resume. The signatures and docstrings are given; you type the rest.
# The package's finished version is tests/test_dataflow_memory.py::test_resume_after_restart (two savers, one file).
THREAD = {"configurable": {"thread_id": "lab-13-2"}}


def start(db_path: Path) -> None:
    """Turn one on a fresh SQLite file, then die on the spot: no clean shutdown, as if the process were killed."""
    for leftover in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        leftover.unlink(missing_ok=True)
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        desk = build_v3_memory(checkpointer=saver, model=chat)
        first = desk.invoke(turn(TURN_ONE), THREAD, context=CONTEXT)
        print("process", os.getpid(), "turn 1 turns", first["turns"], "reply", first["reply"])
        print("checkpoints_after_turn_1", len(list(desk.get_state_history(THREAD))))
        print("process", os.getpid(), "dies now", flush=True)
        os._exit(0)


def resume(db_path: Path) -> None:
    """A new process, a new saver on the same file: read what turn one left, count its rows, run turn two."""
    thread = THREAD
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        desk = build_v3_memory(checkpointer=saver, model=chat)
        saved = desk.get_state(thread).values
        print("process", os.getpid(), "saved turns", saved.get("turns"), "reply", saved.get("reply"))
        sql = "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?"
        print("rows_in_file", saver.conn.execute(sql, (thread["configurable"]["thread_id"],)).fetchone()[0])
        second = desk.invoke(turn(TURN_TWO), thread, context=CONTEXT)
        print("turn 2 turns", second["turns"], "reply", second["reply"])


# BREAK: in resume, change thread = THREAD to thread = {"configurable": {"thread_id": "lab-13-2-other"}} and run
# --start, then --resume. Nothing fails. The saved notebook is empty (turns None), the file has 0 rows for that
# thread, and turn two runs with turns 1: no memory of turn one, though the reply may still read fine. The
# turn-one notebook is filed under another thread id. Put it back and run --start, then --resume.

# %%
if FLAG:
    print("db", DB_PATH.as_posix())
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if FLAG == "--start":
    start(DB_PATH)
elif FLAG == "--resume":
    resume(DB_PATH)
else:
    print("next: python labs/06_04_03_sqlite_kill_and_resume.py --start, then the same with --resume")
