# %%
"""Lab 29.4: least-privilege scopes, tool by tool.

What we build: a scope on every tool of the orders server. You type the scope map (lookup_order needs
orders:read, refund needs orders:refund) and the few lines that put each tool behind its scope on the
HTTP build. Then two clerks call the server: one whose token carries only orders:read, one whose token
also carries orders:refund.

What you learn: a scope says what this caller may ever do; the person in front of the refund (lab 29.8)
decides whether this one call happens now. A company wants both. A desk asks for the scopes it needs and
no more, and a wildcard scope like full-access is on the MCP security best practices page's list of common mistakes. Scopes
go on the HTTP build only: a tool with a scope rule is hidden from any client that has no token, so on
the stdio server of Section 28 the refund would simply disappear. On this FastMCP a scope the token lacks
hides the tool, so the caller sees "Unknown tool", not an HTTP 403.

What will be true on your screen: the versions; the scope each tool needs; the read-only clerk seeing
only lookup_order and getting "Unknown tool" for the refund, with the raw answer on the wire; the refund
clerk seeing both tools and the refund writing one ledger row.
"""

from pathlib import Path
from importlib.metadata import version
import json
import os
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import httpx
from fastmcp import Client, FastMCP
from fastmcp.server.auth import require_scopes

from dataflow.mcp.auth import ISSUER, build_auth, mint, stand_in_keys
from dataflow.mcp.http import ANNOTATIONS, envelope, free_port, mcp_headers, start_http, url_for
from dataflow.mcp.runtime import run_async
from dataflow.mcp.server import lookup_order, refund
from dataflow.tools.refund import read_refunds

print("mcp", version("mcp"), "fastmcp", version("fastmcp"))

# The refund writes a ledger row. A temp ledger keeps the real one clean.
ledger = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
ledger.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = ledger.name


# %%
# TYPE THIS: TOOL_SCOPES and scoped_server. The signature and docstring are given; you type the rest.
# Their finished copies are TOOL_SCOPES and build_http_server in dataflow/mcp/http.py.
TOOL_SCOPES = {
    "lookup_order": "orders:read",
    "refund": "orders:refund",
}


def scoped_server(scopes: dict, auth) -> FastMCP:
    """The orders server for HTTP, each tool behind the one scope its entry in scopes names."""
    server = FastMCP("dataflow", auth=auth)
    for fn in (lookup_order, refund):
        name = fn.__name__
        server.tool(fn, annotations=ANNOTATIONS[name], auth=require_scopes(scopes[name]))
    return server


# BREAK: a copy-paste slip. Change "orders:refund" in TOOL_SCOPES to "orders:read" and run. The read-only
# clerk now sees the refund and the refund writes a ledger row. Put it back and run.


# %%
keys = stand_in_keys()
port = free_port()
url = url_for(port)
auth = build_auth(keys.public_key, ISSUER, url, f"http://127.0.0.1:{port}")
url, stop = start_http(scoped_server(TOOL_SCOPES, auth), port)
for name, scope in TOOL_SCOPES.items():
    print("needs", name, scope)

CLERKS = {
    "read_only_clerk": ["orders:read"],
    "refund_clerk": ["orders:read", "orders:refund"],
}


async def as_clerk(label: str, token: str) -> None:
    """List the tools this token can see, then try the refund."""
    async with Client(url, auth=token) as client:
        print(label, "sees", [tool.name for tool in await client.list_tools()])
        try:
            result = await client.call_tool("refund", {"order_id": "DF-1001", "amount": 49.0, "reason": "unused lamp"})
            print(label, "refund", json.dumps(result.data))
        except Exception as exc:
            print(label, "refund_refused", type(exc).__name__, str(exc))


for label, scopes in CLERKS.items():
    before = len(read_refunds())
    token = mint(keys, audience=url, scopes=scopes, subject=label)
    print(label, "token_scopes", scopes)
    run_async(as_clerk(label, token))
    print(label, "ledger_rows_added", len(read_refunds()) - before)

# %%
# The same refused call, by hand, to see what the wire says for a scope the token lacks.
token = mint(keys, audience=url, scopes=CLERKS["read_only_clerk"], subject="read_only_clerk")
body = envelope("tools/call", {"name": "refund", "arguments": {"order_id": "DF-1001", "amount": 49.0, "reason": "unused lamp"}}, 1)
reply = httpx.post(url, json=body, headers=mcp_headers(body, token), timeout=10)
answer = reply.json()["result"]
print("wire status", reply.status_code)
print("wire isError", answer["isError"])
print("wire text", answer["content"][0]["text"])

# %%
print("server_stopped", stop())
