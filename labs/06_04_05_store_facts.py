# %% [markdown]
# The store: facts across threads.
#
# When this works, a preference written on thread A is read on a new
# thread B for the same customer. A different customer has a miss.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

import config
from dataflow.graphs.v1_triage import DeskContext
from dataflow.graphs.v3_memory import (
    PREFERENCE_KEY,
    build_v3_memory,
    preference_namespace,
)

print("model", config.CHAT_MODEL)

store = InMemoryStore()
saver = InMemorySaver()
graph = build_v3_memory(checkpointer=saver, store=store)

customer_a = "C-2001"
customer_c = "C-2099"
pref_text = "please always email me, never call"
follow_text = "Where is order DF-1001?"
other_text = "What is your return window?"

# %%
thread_a = {"configurable": {"thread_id": "lab-10-5-a"}}
out_a = graph.invoke(
    {"ticket": pref_text, "messages": [HumanMessage(content=pref_text)]},
    thread_a,
    context=DeskContext(customer_id=customer_a),
)
print("thread", "lab-10-5-a")
print("customer_id", customer_a)
print("turn_a_text", pref_text)
print("reply_a", out_a.get("reply"))
print("preference_a", out_a.get("preference"))

namespace = preference_namespace(customer_a)
print("store_namespace", namespace)
hits = store.search(namespace)
print("store_hits", len(hits))
for item in hits:
    print("store_item", item.key, item.value)

# %%
thread_b = {"configurable": {"thread_id": "lab-10-5-b"}}
out_b = graph.invoke(
    {"ticket": follow_text, "messages": [HumanMessage(content=follow_text)]},
    thread_b,
    context=DeskContext(customer_id=customer_a),
)
print("thread", "lab-10-5-b")
print("customer_id", customer_a)
print("reply_b", out_b.get("reply"))
print("preference_b", out_b.get("preference"))

# %%
thread_c = {"configurable": {"thread_id": "lab-10-5-c"}}
out_c = graph.invoke(
    {"ticket": other_text, "messages": [HumanMessage(content=other_text)]},
    thread_c,
    context=DeskContext(customer_id=customer_c),
)
pref_c = out_c.get("preference")
print("thread", "lab-10-5-c")
print("customer_id", customer_c)
print("reply_c", out_c.get("reply"))
print("thread_c_preference", pref_c)
print("miss", pref_c is None or pref_c == {})
item_c = store.get(preference_namespace(customer_c), PREFERENCE_KEY)
print("store_c", None if item_c is None else item_c.value)
