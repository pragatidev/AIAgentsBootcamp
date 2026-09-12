# %%
"""S6.5 One happy path, one miss. No crash on unknown id."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.tools.orders import lookup_order_by_id

# %%
hit = lookup_order_by_id("DF-1001")
print("hit_found", hit["found"])
print("hit_item", hit.get("item"))

# %%
miss = lookup_order_by_id("DF-9999")
print("miss_found", miss["found"])
print("miss_reason", miss.get("reason"))
