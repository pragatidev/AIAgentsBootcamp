# %% [markdown]
# Store a customer preference and read it on a new thread.
#
# Reuse the DataFlow store: file on thread A, read on thread B, miss on
# customer C. Then a profile with dates, sources, a lifetime per key,
# and a forget path.

# %%
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone

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
from dataflow.memory.profile import forget, put_profile, read_profile

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
thread_a = {"configurable": {"thread_id": "lab-5-7-a"}}
out_a = graph.invoke(
    {"ticket": pref_text, "messages": [HumanMessage(content=pref_text)]},
    thread_a,
    context=DeskContext(customer_id=customer_a),
)
print("thread", "lab-5-7-a")
print("preference_a", out_a.get("preference"))

thread_b = {"configurable": {"thread_id": "lab-5-7-b"}}
out_b = graph.invoke(
    {"ticket": follow_text, "messages": [HumanMessage(content=follow_text)]},
    thread_b,
    context=DeskContext(customer_id=customer_a),
)
print("thread", "lab-5-7-b")
print("preference_b", out_b.get("preference"))

thread_c = {"configurable": {"thread_id": "lab-5-7-c"}}
out_c = graph.invoke(
    {"ticket": other_text, "messages": [HumanMessage(content=other_text)]},
    thread_c,
    context=DeskContext(customer_id=customer_c),
)
pref_c = out_c.get("preference")
print("thread", "lab-5-7-c")
print("thread_c_preference", pref_c)
print("miss", pref_c is None or pref_c == {})
item_c = store.get(preference_namespace(customer_c), PREFERENCE_KEY)
print("store_c", None if item_c is None else item_c.value)

# %%
profiles = InMemoryStore()
now = datetime.now(timezone.utc)
put_profile(
    profiles,
    customer_a,
    "contact_channel",
    "email",
    source="stated",
    written_at=now,
)
put_profile(
    profiles,
    customer_a,
    "mood",
    "angry last Tuesday",
    source="stated",
    written_at=now - timedelta(days=8),
)
read_now = read_profile(profiles, customer_a, now=now)
print("profile_after_read", read_now["profile"])
print("stale_dropped", read_now["dropped"])
print("stale_key_dropped", "mood" in read_now["dropped"])
deleted = forget(profiles, customer_a)
print("forget_deleted", deleted)
empty = read_profile(profiles, customer_a, now=now)
print("after_forget", empty["profile"])
print("forget_emptied", empty["profile"] == {})
