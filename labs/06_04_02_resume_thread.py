# %% [markdown]
# Resume a thread with an in-memory checkpointer.
#
# When this works, turn two on the same thread_id continues turn one.
# The same follow-up on a new thread does not.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

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
print("model", config.CHAT_MODEL)
print("turn_ticket_ids", ["T-3001", "T-3028"])
print("chosen T-3001", turn_one["text"])
print("chosen T-3028", turn_two["text"])
print("customer_id", turn_one["customer_id"])


def checkpoint_count(graph, thread_config) -> int:
    return len(list(graph.get_state_history(thread_config)))


# %%
saver = InMemorySaver()
graph = build_v3_memory(checkpointer=saver)
context = DeskContext(customer_id=turn_one["customer_id"])
same_thread = {"configurable": {"thread_id": "lab-10-2"}}

first = graph.invoke(
    {
        "ticket": turn_one["text"],
        "messages": [HumanMessage(content=turn_one["text"])],
    },
    same_thread,
    context=context,
)
print("thread", "lab-10-2")
print("turn", 1)
print("reply1", first.get("reply"))
print("checkpoints_after_turn_1", checkpoint_count(graph, same_thread))

second = graph.invoke(
    {
        "ticket": turn_two["text"],
        "messages": [HumanMessage(content=turn_two["text"])],
    },
    same_thread,
    context=context,
)
print("turn", 2)
print("reply1", first.get("reply"))
print("reply2", second.get("reply"))
print("checkpoints_after_turn_2", checkpoint_count(graph, same_thread))

# %%
fresh = {"configurable": {"thread_id": "lab-10-2-fresh"}}
fresh_out = graph.invoke(
    {
        "ticket": turn_two["text"],
        "messages": [HumanMessage(content=turn_two["text"])],
    },
    fresh,
    context=context,
)
print("new_thread", "lab-10-2-fresh")
print("new_thread_reply", fresh_out.get("reply"))
