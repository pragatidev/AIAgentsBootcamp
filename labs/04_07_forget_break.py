# %% [markdown]
# Break for lab 5.7: forget the profile, then read on a new thread.
#
# Thread x stores the customer's preference. forget() deletes the namespace
# and returns the keys it removed. Thread y then asks about an order and the
# desk holds no preference: preference_after_forget is None and the store
# lookup returns None. Each step prints before it runs so a stall has a name.

# %%
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from dataflow.graphs.v1_triage import DeskContext
from dataflow.graphs.v3_memory import PREFERENCE_KEY, build_v3_memory, preference_namespace
from dataflow.memory.profile import forget

store = InMemoryStore()
g = build_v3_memory(checkpointer=InMemorySaver(), store=store)
cid = "C-2001"

# %%
print("step", "store on thread lab-5-7-x")
t = time.time()
g.invoke(
    {
        "ticket": "please always email me, never call",
        "messages": [HumanMessage(content="please always email me, never call")],
    },
    {"configurable": {"thread_id": "lab-5-7-x"}},
    context=DeskContext(customer_id=cid),
)
print("step_secs", round(time.time() - t, 1))
print("stored_before_forget", store.get(preference_namespace(cid), PREFERENCE_KEY).value)

# %%
print("step", "forget")
print("forget_deleted", forget(store, cid))

# %%
print("step", "read on thread lab-5-7-y")
t = time.time()
out = g.invoke(
    {
        "ticket": "Where is order DF-1001?",
        "messages": [HumanMessage(content="Where is order DF-1001?")],
    },
    {"configurable": {"thread_id": "lab-5-7-y"}},
    context=DeskContext(customer_id=cid),
)
print("step_secs", round(time.time() - t, 1))
print("preference_after_forget", out.get("preference"))
print("store_after_forget", store.get(preference_namespace(cid), PREFERENCE_KEY))
