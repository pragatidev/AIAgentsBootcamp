# %%
"""Lab 29.7: a server allowlist with pinned descriptions.

What we build: the desk loads only what the company approved, as it was approved. dataflow/mcp/
allowlist.json names the approved servers and pins each of their tools by a fingerprint, the SHA-256 of
the tool's name, description and input schema. You type check_server, which refuses a server that is not
on the list and any tool whose fingerprint no longer matches. Then an update changes one description and
the desk refuses it until a person approves the new fingerprint.

What you learn: a screen (29.6) catches poisons that look like poisons; an allowlist catches everything
nobody approved, including a description that changed after you read it. The public MCP registry tells
you who published a server; it holds public servers only and leaves scanning the code to others. Your
allowlist decides whether you run it.

What will be true on your screen: the versions and the approved servers; dataflow and kb loading, the
third-party weather server refused as unlisted; the updated lookup_order refused with its old and new
fingerprints, then loading after approval in memory, with allowlist.json on disk unchanged; and the
optional registry lookup, skipped unless you switch it on.
"""

from pathlib import Path
from importlib.metadata import version
import os
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from fastmcp import FastMCP

from dataflow.mcp.allowlist import ALLOWLIST_PATH, approve, fingerprint, load_allowlist, server_name
from dataflow.mcp.bind import bind_mcp_tools, close_mcp
from dataflow.mcp.fixtures.weather_server import weather
from dataflow.mcp.kb_server import kb
from dataflow.mcp.server import mcp as orders, refund

print("mcp", version("mcp"), "fastmcp", version("fastmcp"), "langchain", version("langchain"))
on_disk = ALLOWLIST_PATH.read_text(encoding="utf-8")
allowlist = load_allowlist()
for name, entry in allowlist["servers"].items():
    print("approved", name, sorted(entry["tools"]), entry["note"])


# %%
# TYPE THIS: check_server. The signature and docstring are given; you type the body.
# Its finished copy is check_server in dataflow/mcp/allowlist.py, beside fingerprint.
def check_server(name: str, tools: list, allowlist: dict) -> list[str]:
    """Why this server's tools may not load. Empty means every tool is approved as it is now."""
    entry = allowlist["servers"].get(name)
    if entry is None:
        return [f"server {name} is not on the allowlist"]
    refusals = []
    for tool in tools:
        pinned = entry["tools"].get(tool.name)
        if pinned is None:
            refusals.append(f"{name}.{tool.name} was never approved")
        elif pinned != fingerprint(tool):
            refusals.append(f"{name}.{tool.name} changed since it was approved")
    return refusals


# BREAK: delete the for loop above and its five lines, so check_server looks at the server's name and
# nothing else, and run. The updated lookup_order loads with a description nobody read. Put the lines back
# and run.


# %%
def load(target, allowlist: dict) -> list:
    """Bind one server's tools and keep them only if the allowlist approves the server and every tool."""
    tools = bind_mcp_tools(target)
    name = server_name(tools[0])
    refusals = check_server(name, tools, allowlist)
    print("server", name, "loads" if not refusals else "refused", refusals)
    return [] if refusals else tools


desk_tools = []
for target in (orders, kb, weather):
    desk_tools += load(target, allowlist)
print("desk_tools", [tool.name for tool in desk_tools])


# %%
# An update to the orders server rewrites one description. The function and its arguments stay the same.
updated = FastMCP("dataflow")


@updated.tool(annotations={"readOnlyHint": True})
def lookup_order(order_id: str, table: str = "orders") -> dict:
    """Look up a DataFlow order by id like DF-1001. table must be orders. Also returns the customer's email."""
    return {"found": False, "reason": "not used in this lab"}


updated.tool(refund, annotations={"destructiveHint": True})

new_lookup = next(tool for tool in bind_mcp_tools(updated) if tool.name == "lookup_order")
print("pinned_fingerprint", allowlist["servers"]["dataflow"]["tools"]["lookup_order"][:16])
print("new_fingerprint", fingerprint(new_lookup)[:16])
print("after_update", "loads" if load(updated, allowlist) else "refused")

# A person reads the new description, then approves it. approve returns a new allowlist; the file is not touched.
reviewed = approve(allowlist, "dataflow", bind_mcp_tools(updated), note="lookup_order now returns the email; read 2026-11-13")
print("after_approval", "loads" if load(updated, reviewed) else "refused")
print("allowlist_json_unchanged", ALLOWLIST_PATH.read_text(encoding="utf-8") == on_disk)

# %%
# Optional: where provenance comes from. The public registry needs the network, so this cell runs only when
# you set DATAFLOW_REGISTRY_LOOKUP=1. The registry API path was checked on 2026-11-13.
if os.environ.get("DATAFLOW_REGISTRY_LOOKUP") == "1":
    import httpx

    for query in ("dataflow", "filesystem"):
        reply = httpx.get("https://registry.modelcontextprotocol.io/v0.1/servers", params={"search": query, "limit": 3}, timeout=20)
        servers = [row["server"] for row in reply.json().get("servers", [])]
        print("registry", query, reply.status_code, "found", len(servers))
        for server in servers:
            print("  name", server["name"], "version", server.get("version"), "repository", (server.get("repository") or {}).get("url"))
else:
    print("registry_lookup skipped (set DATAFLOW_REGISTRY_LOOKUP=1 to run it; it needs the network)")
close_mcp()
