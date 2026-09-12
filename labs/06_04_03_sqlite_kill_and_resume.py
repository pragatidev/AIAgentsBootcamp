# %% [markdown]
# SQLite checkpointer: kill the process and resume.
#
# `python labs/06_04_03_sqlite_kill_and_resume.py --start` writes turn one
# to dataflow/data/checkpoints.sqlite and exits.
# `python labs/06_04_03_sqlite_kill_and_resume.py --resume` opens a fresh
# saver on that file, prints the saved reply, then runs turn two.

# %%
from pathlib import Path
import argparse
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

import config
from dataflow.graphs.v1_triage import DeskContext
from dataflow.graphs.v3_memory import build_v3_memory

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

turn_one = by_id["T-3001"]
turn_two = by_id["T-3028"]
db_path = root / "dataflow" / "data" / "checkpoints.sqlite"
thread = {"configurable": {"thread_id": "lab-10-3"}}
context = DeskContext(customer_id=turn_one["customer_id"])

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("--start", action="store_true")
group.add_argument("--resume", action="store_true")
args, _ = parser.parse_known_args()

print("model", config.CHAT_MODEL)
print("db", db_path.as_posix())
print("thread", "lab-10-3")


def checkpoint_count(graph, thread_config) -> int:
    return len(list(graph.get_state_history(thread_config)))


# %%
if args.start:
    print("phase", "start")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for extra in ("", "-wal", "-shm"):
        leftover = Path(str(db_path) + extra)
        if leftover.exists():
            leftover.unlink()
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        saver.setup()
        graph = build_v3_memory(checkpointer=saver)
        first = graph.invoke(
            {
                "ticket": turn_one["text"],
                "messages": [HumanMessage(content=turn_one["text"])],
            },
            thread,
            context=context,
        )
        print("turn", 1)
        print("reply1", first.get("reply"))
        print("checkpoints_after_turn_1", checkpoint_count(graph, thread))
elif args.resume:
    print("phase", "resume")
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        saver.setup()
        graph = build_v3_memory(checkpointer=saver)
        saved = graph.get_state(thread)
        saved_values = saved.values if saved else {}
        print("state_reply", saved_values.get("reply"))
        print("state_ticket", saved_values.get("ticket"))
        print("state_turns", saved_values.get("turns"))
        second = graph.invoke(
            {
                "ticket": turn_two["text"],
                "messages": [HumanMessage(content=turn_two["text"])],
            },
            thread,
            context=context,
        )
        print("turn", 2)
        print("reply2", second.get("reply"))
        print("checkpoints_after_turn_2", checkpoint_count(graph, thread))
else:
    print("usage", "--start or --resume")
