# %% [markdown]
# Write a FastMCP server for DataFlow lookup.
#
# When this works, the tool schema prints, an in-process call returns
# DF-1001, a planted copy accepts table customers and reads nothing
# useful, and the committed tool returns a typed miss.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.mcp.server import (
    call_tool,
    list_tool_schemas,
    lookup_order_open,
    read_returns_policy,
    render_decline,
)

print("model", config.CHAT_MODEL)
schemas = list_tool_schemas()
lookup_schema = next(row for row in schemas if row["name"] == "lookup_order")
print("tool_schema")
print(json.dumps(lookup_schema["input_schema"], indent=2))
print("in_process")
row = call_tool("lookup_order", {"order_id": "DF-1001"})
print(row)
print("resource_heading", read_returns_policy().splitlines()[0])
print("prompt", render_decline("DF-1001", "outside the window"))

# %%
print("cell", "break")
print("BREAK: planted copy accepts table customers and reads nothing useful")
planted = lookup_order_open("DF-1001", table="customers")
print("planted_customers", planted)

# %%
print("cell", "fix")
print("FIX: committed tool returns a typed miss for an unknown table")
miss = call_tool("lookup_order", {"order_id": "DF-1001", "table": "customers"})
print("unknown_table", miss)
