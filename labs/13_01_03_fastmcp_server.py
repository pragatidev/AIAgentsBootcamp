# %%
"""Lab 28.5: write a FastMCP server for the DataFlow order lookup.

What we build: the orders team's server and its first tool. You type lookup_order, with its docstring,
its type hints and the guard that answers a typed miss for any table but orders, and register it on a
server of your own with a read-only annotation. Then a client calls it in process.

What you learn: FastMCP turns a plain Python function into an MCP tool. The docstring becomes the
description the model reads, the type hints become the input schema, the returned dict becomes
structuredContent, and the annotation is a promise the server makes, which a client may only believe if
it trusts the server. The guard is yours to write: the schema says table is a string, so any string
gets in.

What will be true on your screen: the description, the input and output schemas FastMCP derived and the
annotation; the row for DF-1001, called in process; and a typed miss for table customers.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from fastmcp import Client, FastMCP

from dataflow.mcp.runtime import run_async
from dataflow.tools.orders import lookup_order_by_id

TABLES = {"orders"}
lab = FastMCP("dataflow-lab")


# %%
# TYPE THIS: lookup_order. The decorator, signature and docstring are given; you type the body.
# Its finished copy is lookup_order in dataflow/mcp/server.py.
@lab.tool(annotations={"readOnlyHint": True})
def lookup_order(order_id: str, table: str = "orders") -> dict:
    """Look up a DataFlow order by id like DF-1001. table must be orders."""
    if table not in TABLES:
        return {"found": False, "reason": "unknown table"}
    return lookup_order_by_id(order_id)


# BREAK: delete the two guard lines (the if and its return) above and run. The call with table customers is
# accepted and comes back as DF-1001's row, which looks like an answer to a question nobody can ask of this
# server. Put the guard back and run: the miss is typed again.


# %%
# A client in the same process: Client(lab) talks to the server object directly, no child, no wire.
async def describe_and_call() -> None:
    async with Client(lab) as client:
        tool = (await client.list_tools())[0]
        print("tool", tool.name)
        print("description", tool.description)
        print("input_schema", json.dumps(tool.input_schema, indent=2))
        print("output_schema", json.dumps(tool.output_schema))
        print("annotations read_only_hint", tool.annotations.read_only_hint)
        row = await client.call_tool("lookup_order", {"order_id": "DF-1001"})
        print("DF-1001 structured_content", row.structured_content)
        other = await client.call_tool("lookup_order", {"order_id": "DF-1001", "table": "customers"})
        print("table customers", other.structured_content)


run_async(describe_and_call())
