"""DataFlow FastMCP server: lookup, returns policy, wiki pages, decline prompt, refund write.

The refund tool writes and nothing else. The desk in front of it holds the gate."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError

from dataflow.mcp.runtime import run_async
from dataflow.tools.orders import lookup_order_by_id
from dataflow.tools.refund import write_refund

DATAFLOW = Path(__file__).resolve().parents[1]
POLICY_PATH = DATAFLOW / "wiki" / "return_policy.md"
PID_PATH = Path(__file__).resolve().parent / "runs" / "server.pid"
TABLES = {"orders"}
DECLINE_TEMPLATE = (
    "We cannot refund order {order_id}. Reason: {reason}."
)

mcp = FastMCP("dataflow")


@mcp.tool(annotations={"readOnlyHint": True})
def lookup_order(order_id: str, table: str = "orders") -> dict:
    """Look up a DataFlow order by id like DF-1001. table must be orders."""
    if table not in TABLES:
        return {"found": False, "reason": "unknown table"}
    return lookup_order_by_id(order_id)


@mcp.resource("dataflow://policy/returns")
def returns_policy() -> str:
    """The DataFlow returns policy page."""
    return POLICY_PATH.read_text(encoding="utf-8")


@mcp.prompt
def decline_refund(order_id: str, reason: str) -> str:
    """A decline template for a refund reply."""
    return DECLINE_TEMPLATE.format(order_id=order_id, reason=reason)


WIKI_DIR = DATAFLOW / "wiki"


@mcp.resource("dataflow://wiki/{page}")
def wiki_page(page: str) -> str:
    """One DataFlow help page by file name, like return_policy.md. A name outside the wiki folder is refused."""
    path = (WIKI_DIR / page).resolve()
    if not path.is_relative_to(WIKI_DIR.resolve()) or not path.is_file():
        raise ResourceError(f"no wiki page named {page!r}")
    return path.read_text(encoding="utf-8")


@mcp.tool(annotations={"destructiveHint": True})
def refund(order_id: str, amount: float, reason: str) -> dict:
    """Issue a pretend refund. Writes one ledger row. No gate inside this tool."""
    return write_refund(order_id, amount, reason)


def call_tool(name: str, arguments: dict | None = None) -> object:
    """Call one tool in process through the FastMCP client."""
    from fastmcp import Client

    async def _go():
        async with Client(mcp) as client:
            result = await client.call_tool(name, arguments or {})
            return result.data

    return run_async(_go())


def list_tool_schemas() -> list[dict]:
    """JSON schemas FastMCP derives for each tool. In process."""
    from fastmcp import Client

    async def _go():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            rows = []
            for tool in tools:
                schema = getattr(tool, "input_schema", None)
                rows.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": schema,
                    }
                )
            return rows

    return run_async(_go())


def read_returns_policy() -> str:
    """Read the returns resource in process."""
    from fastmcp import Client

    async def _go():
        async with Client(mcp) as client:
            contents = await client.read_resource("dataflow://policy/returns")
            first = contents[0]
            return str(getattr(first, "text", "") or "")

    return run_async(_go())


def render_decline(order_id: str, reason: str) -> str:
    """Render the decline prompt in process."""
    from fastmcp import Client

    async def _go():
        async with Client(mcp) as client:
            prompt = await client.get_prompt(
                "decline_refund",
                {"order_id": order_id, "reason": reason},
            )
            messages = list(getattr(prompt, "messages", None) or [])
            if not messages:
                return ""
            content = getattr(messages[0], "content", None)
            return str(getattr(content, "text", "") or content or "")

    return run_async(_go())


if __name__ == "__main__":
    os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    sys.stderr.write("dataflow_mcp_pid " + str(os.getpid()) + "\n")
    sys.stderr.flush()
    try:
        mcp.run(transport="stdio", show_banner=False)
    finally:
        if PID_PATH.is_file():
            PID_PATH.unlink()
