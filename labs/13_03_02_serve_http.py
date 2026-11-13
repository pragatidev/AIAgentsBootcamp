# %%
"""Lab 29.2: serve the DataFlow server over Streamable HTTP.

What we build: the orders server as a URL. You type the lines that turn the server into a web app and
start it on 127.0.0.1 in a background thread, and the function that writes the headers every request
carries. A FastMCP client connects to the URL; then you send requests by hand with httpx and read every
header that goes out and comes back.

What you learn: over HTTP every MCP message is one POST to one endpoint. The request carries headers
that mirror its body (the protocol version, the method, and for a tool call the tool's name) so a
gateway can route and inspect a request without reading the body. The body stays the truth, so a server
refuses a request whose header disagrees with it. Revision 2026-07-28 has no session: no
Mcp-Session-Id goes out or comes back.

What will be true on your screen: the versions; the URL and protocol_version 2026-07-28 from a real
client; for each request by hand, the headers sent, the status, the response headers (no session id)
and the result; a refund sent by hand writing one row to a temp ledger; and the server stopped.
"""

from pathlib import Path
from importlib.metadata import version
import json
import os
import sys
import tempfile
import threading
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import httpx
import uvicorn
from fastmcp import Client, FastMCP

from dataflow.mcp.http import build_http_server, envelope, free_port
from dataflow.mcp.runtime import run_async
from dataflow.tools.refund import read_refunds

print("mcp", version("mcp"), "fastmcp", version("fastmcp"), "uvicorn", version("uvicorn"))

# The refund writes a ledger row. A temp ledger keeps the real one clean.
ledger = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
ledger.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = ledger.name


# %%
# TYPE THIS: serve_http. The signature and docstring are given; you type the body.
# Its finished copy is serve() in dataflow/mcp/http.py.
def serve_http(server: FastMCP, port: int) -> tuple:
    """Serve server over Streamable HTTP on 127.0.0.1:port in a background thread. Return its URL and a stop function."""
    app = server.http_app(path="/mcp")
    web = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=web.run, daemon=True)
    thread.start()
    while not web.started and thread.is_alive():
        time.sleep(0.05)

    def stop() -> bool:
        web.should_exit = True
        thread.join(timeout=5)
        return not thread.is_alive()

    return f"http://127.0.0.1:{port}/mcp", stop


# %%
# TYPE THIS: mcp_headers. The signature and docstring are given; you type the body.
# Its finished copy, which also adds the bearer token of lab 29.3, is mcp_headers in dataflow/mcp/http.py.
def mcp_headers(body: dict) -> dict:
    """The headers one Streamable HTTP request carries, each one mirroring a field of the body."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": body["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"],
        "Mcp-Method": body["method"],
    }
    if "name" in body["params"]:
        headers["Mcp-Name"] = body["params"]["name"]
    return headers


# BREAK: replace the Mcp-Name line above with headers["Mcp-Name"] = "lookup_order", a header that no
# longer looks at the body, and run. The lookup still answers, because its header happens to be true.
# The refund is refused with status 400 and error -32020, and the ledger stays empty: a gateway that let
# lookups through and blocked refunds by this header would have been lied to, so the server checks it.
# Put the line back and run.


# %%
# The server from dataflow/mcp/http.py: the same lookup_order and refund as the stdio server, no token yet.
url, stop = serve_http(build_http_server(), free_port())
print("url", url)


async def connect(url: str) -> tuple:
    async with Client(url) as client:
        return client.protocol_version, [tool.name for tool in await client.list_tools()]


protocol_version, names = run_async(connect(url))
print("protocol_version", protocol_version)
print("tools", names)


# %%
def post(body: dict) -> dict:
    """Send one request by hand and print what went out and what came back."""
    headers = mcp_headers(body)
    reply = httpx.post(url, json=body, headers=headers, timeout=10)
    print("request", body["method"], body["params"].get("name", ""))
    for name in ("MCP-Protocol-Version", "Mcp-Method", "Mcp-Name", "Accept"):
        if name in headers:
            print("  sent", name, headers[name])
    print("  status", reply.status_code)
    print("  response_headers", dict(reply.headers))
    print("  session_id_header", "mcp-session-id" in reply.headers)
    answer = reply.json()
    if "error" in answer:
        print("  error", answer["error"]["code"], answer["error"]["message"])
    return answer


answer = post(envelope("server/discover", None, 1))
if "result" in answer:
    print("  supportedVersions", answer["result"]["supportedVersions"])
answer = post(envelope("tools/call", {"name": "lookup_order", "arguments": {"order_id": "DF-1001"}}, 2))
if "result" in answer:
    print("  structuredContent", json.dumps(answer["result"]["structuredContent"]))
answer = post(envelope("tools/call", {"name": "refund", "arguments": {"order_id": "DF-1001", "amount": 49.0, "reason": "unused lamp"}}, 3))
if "result" in answer:
    print("  structuredContent", json.dumps(answer["result"]["structuredContent"]))
print("ledger_rows", len(read_refunds()))

# %%
print("server_stopped", stop())
