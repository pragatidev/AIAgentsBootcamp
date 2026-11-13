# %%
"""Lab 13.3: the store, facts across threads.

What we build: you type the two nodes that keep a customer's contact preference on the store, reached from
inside the graph through the runtime: write_pref_node asks the model whether the ticket states a preference and
puts it on the customer's shelf when it does, read_pref_node takes it off the shelf, and owner says which shelf,
("customers", customer_id). A given builder wires read then write, compiled with a checkpointer and a store.
Then three threads: C-2001 states a preference on thread A, C-2001 asks about an order on thread B, and C-2099
asks about returns on thread C. Last, the package desk speaks on a new thread with what the shelf holds.

What you learn: the thread is one conversation; the store is facts that outlive it. Compiled with store=,
LangGraph hands the store to every node through runtime.store, and the namespace you pick decides who finds a
fact again. Keyed by the customer, thread B finds what thread A wrote and another customer finds nothing. Keyed
by the thread, the fact is lost the moment the conversation ends. Section 6 taught this store on create_agent;
here it is the same store, reached from a node you wrote.

What will be true on your screen: the model line and the versions; thread A: no preference read, then
{'channel': 'email', 'stated': True} written, and the store's one item on ('customers', 'C-2001'); thread B: the
same preference read with nothing new written; thread C: None, a miss; the desk's reply on thread B's question
naming email; then the search note: 10 of 12 items with no word about the other 2, all 12 with limit=20.
"""

from importlib.metadata import version
from pathlib import Path
import sys
from typing import Any, TypedDict

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_config  # the BREAK uses it
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.v3_memory import PREFERENCE_KEY, PREFERENCE_SYSTEM, PreferenceDecision, build_v3_memory

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


class StoreState(TypedDict, total=False):
    """The ticket in, the preference the run found or wrote."""
    ticket: str
    preference: dict[str, Any] | None


# %%
# TYPE THIS: owner, read_pref_node and write_pref_node. The signatures and docstrings are given; you type the rest.
# The package's finished version is preference_namespace, read_pref and write_pref in dataflow/graphs/v3_memory.py.
def owner(runtime: Runtime[DeskContext]) -> tuple[str, str]:
    """The shelf a fact sits on: the customer's, so every thread of theirs finds it."""
    return ("customers", runtime.context.customer_id)


def read_pref_node(state: StoreState, runtime: Runtime[DeskContext]) -> dict:
    """Take the customer's saved preference off the store, or None."""
    item = runtime.store.get(owner(runtime), PREFERENCE_KEY)
    return {"preference": dict(item.value) if item is not None else None}


def write_pref_node(state: StoreState, runtime: Runtime[DeskContext]) -> dict:
    """Ask the model whether the ticket states a contact preference; put it on the customer's shelf when it does."""
    llm = runtime.context.model or config.get_chat_model()
    decision = llm.with_structured_output(PreferenceDecision).invoke(
        [{"role": "system", "content": PREFERENCE_SYSTEM}, {"role": "user", "content": state["ticket"]}]
    )
    if not decision.stated or decision.channel not in ("email", "call"):
        return {}
    preference = {"channel": decision.channel, "stated": True}
    runtime.store.put(owner(runtime), PREFERENCE_KEY, preference)
    return {"preference": preference}


# BREAK: in owner, change the return line to return ("customers", get_config()["configurable"]["thread_id"]) and
# run. Nothing fails. Thread A still writes the preference, but onto the shelf ('customers', 'lab-13-3-a'), so
# thread B for the same customer reads None, a miss, and the fact is as good as lost when thread A ends. Put it
# back and run.


def build_store_desk(store):
    """read_pref then write_pref, compiled with a checkpointer and the store."""
    builder = StateGraph(StoreState, context_schema=DeskContext)
    builder.add_node("read_pref", read_pref_node)
    builder.add_node("write_pref", write_pref_node)
    builder.add_edge(START, "read_pref")
    builder.add_edge("read_pref", "write_pref")
    builder.add_edge("write_pref", END)
    return builder.compile(checkpointer=InMemorySaver(), store=store)


# %%
store = InMemoryStore()
desk = build_store_desk(store)
runs = [
    ("lab-13-3-a", "C-2001", "please always email me, never call"),
    ("lab-13-3-b", "C-2001", "Where is order DF-1001?"),
    ("lab-13-3-c", "C-2099", "What is your return window?"),
]
for thread_id, customer, ticket in runs:
    print("thread", thread_id, "customer", customer, "ticket", ticket)
    for update in desk.stream({"ticket": ticket}, {"configurable": {"thread_id": thread_id}},
                              context=DeskContext(customer_id=customer, model=chat), stream_mode="updates"):
        for node, values in update.items():
            print("  ", node, values)
    for item in store.search(("customers",)):
        print("   store", item.namespace, item.key, item.value)

# %%
# The package desk on a new thread for C-2001: it reads the same shelf before it speaks.
follow = runs[1][2]
spoken = build_v3_memory(store=store, model=chat).invoke(
    {"ticket": follow, "messages": [HumanMessage(content=follow)]},
    {"configurable": {"thread_id": "lab-13-3-desk"}},
    context=DeskContext(customer_id="C-2001"),
)
print("desk preference", spoken.get("preference"))
print("desk reply", spoken.get("reply"))

# %%
# The docs' note: search returns at most limit items (10 unless you say) and nothing tells you there were more.
shelf = ("customers", "C-2001", "notes")
for n in range(12):
    store.put(shelf, f"note-{n:02d}", {"n": n})
print("search_default", len(store.search(shelf)), "of 12")
print("search_limit_20", len(store.search(shelf, limit=20)), "of 12")
