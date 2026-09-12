# %% [markdown]
# Memory by similarity: recall from an embedding store.
#
# File three notes for a customer, search with a new ticket's text,
# print the hits with scores and a floor. Stay inside the namespace.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.memory.recall import build_recall_store, file_note, recall

print("embed_model", config.EMBED_MODEL)
print("embed_dims", config.EMBED_DIMS)
store = build_recall_store(dims=config.EMBED_DIMS)
customer = "C-2001"
other = "C-2099"
file_note(
    store,
    customer,
    "csv_upload",
    "Dashboard breaks when they upload a large csv. Seen in June.",
)
file_note(
    store,
    customer,
    "email_pref",
    "Customer asked to be emailed, never called.",
)
file_note(
    store,
    customer,
    "lamp_return",
    "Returned a desk lamp in August. Unused, refunded.",
)
file_note(
    store,
    other,
    "csv_upload",
    "A different customer also has csv upload trouble.",
)

# %%
query = "The upload page is slow when I send a big csv."
floor = 0.3
hits = recall(store, customer, query, floor=floor, limit=5)
print("query", query)
print("floor", floor)
print("hits", len(hits))
for item in hits:
    print("hit", item["key"], "score", round(item["score"], 4), item["value"])
    print("namespace", item["namespace"])
print(
    "stayed_in_namespace",
    all(item["namespace"] == ("customers", customer) for item in hits),
)
other_hits = recall(store, other, query, floor=0.0, limit=5)
print("other_customer_keys", [item["key"] for item in other_hits])
