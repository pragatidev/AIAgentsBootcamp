# %% [markdown]
# The DataFlow desk remembers a customer across two tickets.
#
# Profile read before and written after. A third ticket from another
# customer reads nothing. Print all three.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.store.memory import InMemoryStore

import config
from dataflow.graphs.v3_memory import PreferenceDecision
from dataflow.memory.profile import put_profile, read_profile

SYSTEM = (
    "You are the DataFlow support desk. Answer in one or two short sentences. "
    "If the profile has a contact channel, honour it in the reply."
)


def handle(store, customer_id: str, ticket: str) -> dict:
    before = read_profile(store, customer_id)
    print("customer_id", customer_id)
    print("profile_before", before["profile"])
    model = config.get_local_chat_model(reasoning=False, num_predict=80)
    structured = model.with_structured_output(PreferenceDecision)
    decision = structured.invoke(
        [
            {
                "role": "system",
                "content": (
                    "channel is email, call, or none. stated is true only when "
                    "the customer clearly names a contact preference."
                ),
            },
            {"role": "user", "content": ticket},
        ]
    )
    if getattr(decision, "stated", False) and decision.channel in ("email", "call"):
        put_profile(
            store,
            customer_id,
            "contact_channel",
            decision.channel,
            source="stated",
        )
        print("wrote", "contact_channel", decision.channel, "source", "stated")
    notes = read_profile(store, customer_id)["profile"]
    extra = ""
    channel = (notes.get("contact_channel") or {}).get("value")
    if channel:
        extra = " Saved preference: contact by " + channel + "."
    reply = model.invoke(
        [
            {"role": "system", "content": SYSTEM + extra},
            {"role": "user", "content": ticket},
        ]
    )
    after = read_profile(store, customer_id)
    text = getattr(reply, "content", reply)
    print("reply", text)
    print("profile_after", after["profile"])
    return {"reply": text, "profile": after["profile"]}


store = InMemoryStore()

# %%
print("ticket", 1)
one = handle(
    store,
    "C-2001",
    "Hi, I want to return order DF-1001. Please always email me, never call.",
)

# %%
print("ticket", 2)
two = handle(
    store,
    "C-2001",
    "Where is order DF-1001 now?",
)

# %%
print("ticket", 3)
three = handle(
    store,
    "C-2099",
    "What is your return window?",
)
print("other_customer_reads_nothing", three["profile"] == {})
