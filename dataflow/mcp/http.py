"""The DataFlow orders server over Streamable HTTP (Lectures 29.2, 29.3, 29.4, 29.9).

The same two tools as dataflow/mcp/server.py, lookup_order and refund, with the same annotations, on
a FastMCP server built for HTTP. Scopes and a token check live on this build only: a tool with a
scope rule is hidden from every client that has no token, so on the stdio and in-process server of
Section 28 the refund would vanish.

serve() runs the app with uvicorn in a background thread on 127.0.0.1, so a lab, a test or a notebook
can start a server and call it from the same process.

Run in a terminal (no token check): python -m dataflow.mcp.http --port 8000
"""

from __future__ import annotations

import argparse
import contextlib
import socket
import threading
import time
from collections.abc import Iterator

import uvicorn
from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes

from dataflow.mcp.server import lookup_order, refund

HOST = "127.0.0.1"
PATH = "/mcp"
PROTOCOL_VERSION = "2026-07-28"

# Least privilege, tool by tool (Lecture 29.4): what a caller's token must carry to see and call each tool.
TOOL_SCOPES = {
    "lookup_order": "orders:read",
    "refund": "orders:refund",
}

ANNOTATIONS = {
    "lookup_order": {"readOnlyHint": True},
    "refund": {"destructiveHint": True},
}


def build_http_server(*, auth=None, scopes: dict[str, str] | None = None, middleware: list | None = None) -> FastMCP:
    """A FastMCP server named dataflow with lookup_order and refund, for HTTP.

    auth is a token check (dataflow/mcp/auth.py). scopes maps a tool name to the scope it needs;
    None attaches no scope rule. middleware runs around every request (dataflow/mcp/audit.py).
    """
    server = FastMCP("dataflow", auth=auth, middleware=middleware)
    for fn in (lookup_order, refund):
        name = fn.__name__
        rule = require_scopes(scopes[name]) if scopes else None
        server.tool(fn, annotations=ANNOTATIONS[name], auth=rule)
    return server


def free_port() -> int:
    """A port nothing listens on right now, picked by the operating system."""
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def url_for(port: int) -> str:
    return f"http://{HOST}:{port}{PATH}"


@contextlib.contextmanager
def serve(server: FastMCP, port: int | None = None) -> Iterator[str]:
    """Serve server over Streamable HTTP in a background thread; yield its URL; stop it on exit."""
    port = port or free_port()
    app = server.http_app(path=PATH)
    web = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="warning"))
    thread = threading.Thread(target=web.run, name=f"mcp-http-{port}", daemon=True)
    thread.start()
    url = url_for(port)
    while not web.started:
        if not thread.is_alive():
            raise RuntimeError(f"the MCP server did not start on {url}")
        time.sleep(0.05)
    try:
        yield url
    finally:
        web.should_exit = True
        thread.join(timeout=5)


def mcp_headers(body: dict, token: str | None = None) -> dict[str, str]:
    """The headers a Streamable HTTP request carries, each one mirroring a field of the body."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": body["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"],
        "Mcp-Method": body["method"],
    }
    if "name" in body["params"]:
        headers["Mcp-Name"] = body["params"]["name"]
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def envelope(method: str, params: dict | None, request_id: int) -> dict:
    """One JSON-RPC request with the two _meta keys revision 2026-07-28 asks for (Lecture 28.3)."""
    params = dict(params or {})
    params["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the DataFlow orders server over Streamable HTTP.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print("serving", url_for(args.port), "(no token check; Ctrl+C stops it)", flush=True)
    build_http_server().run(transport="http", host=HOST, port=args.port, path=PATH, show_banner=False)


if __name__ == "__main__":
    main()
