# %%
"""S11.2 Resume a thread. Same thread_id, turns accrue."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from dataflow.graphs.v3_memory import (
    build_v3_memory,
    read_preference,
    remember_preference,
)

# %%
saver = MemorySaver()
graph = build_v3_memory(saver)
config = {"configurable": {"thread_id": "df-desk-1"}}
first = graph.invoke({"ticket": "DF-1001"}, config)
second = graph.invoke({"ticket": "DF-1002"}, config)
print("turns", second.get("turns"))
print("last_ticket", second.get("last_ticket"))

# %%
store = InMemoryStore()
remember_preference(store, "cust-1", "channel", "email")
print("pref", read_preference(store, "cust-1", "channel"))
print("other_thread_pref", read_preference(store, "cust-2", "channel"))
