"""Bind DataFlow MCP tools through langchain.mcp MCPAdapter.

MCPAdapter is beta in LangChain 1.4. It infers the transport from the
target: an in-process FastMCP server, a stdio MCPConfig, or an http URL.
The tools it returns are async only. This module wraps them so the
existing desk `invoke` path still runs.

FastMCP sessions die if the loop that opened them is closed. bind keeps
the adapter connected on the long-lived loop in runtime.py until
close_mcp() runs.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from dataflow.graphs.rag_tool_cycle import build_rag_tool_cycle
from dataflow.mcp.runtime import run_async

_ADAPTERS: list[Any] = []


async def _close_one(adapter: Any) -> None:
    client = getattr(adapter, "client", adapter)
    closer = getattr(client, "close", None)
    if closer is not None:
        await closer()
        return
    aexit = getattr(adapter, "__aexit__", None)
    if aexit is not None:
        await aexit(None, None, None)


def close_mcp() -> None:
    """Disconnect every adapter bind_mcp_tools opened. Labs call this in finally."""
    while _ADAPTERS:
        adapter = _ADAPTERS.pop()
        try:
            run_async(_close_one(adapter))
        except Exception:
            pass


def _sync_wrap(tool: Any) -> Any:
    """MCPAdapter tools have no sync invoke. Wrap so ToolNode.invoke works.

    The call hops onto the long-lived MCP loop so it never hits a closed loop.
    """

    def call(**kwargs: Any) -> Any:
        return run_async(tool.ainvoke(kwargs))

    call.__name__ = str(getattr(tool, "name", "tool"))
    call.__doc__ = str(getattr(tool, "description", "") or call.__name__)
    return StructuredTool.from_function(
        func=call,
        name=str(getattr(tool, "name", "tool")),
        description=str(getattr(tool, "description", "") or call.__name__),
        args_schema=getattr(tool, "args_schema", None),
    )


async def _open_and_list(target: Any) -> tuple[Any, list[Any]]:
    from langchain.mcp import MCPAdapter

    adapter = MCPAdapter(target)
    await adapter.__aenter__()
    try:
        tools = await adapter.list_tools()
    except BaseException:
        await _close_one(adapter)
        raise
    return adapter, tools


def bind_mcp_tools(target: Any = None, *, wrap: bool = True) -> list[Any]:
    """Discover MCP tools and wrap them for the DataFlow desk.

    Default target is the in-process FastMCP server. Pass an MCPConfig dict
    (stdio) or a FastMCP Client for the lab path.

    wrap=True (tests, invoke) makes ToolNode.invoke work. The adapter stays
    connected on the long-lived loop until close_mcp(). wrap=False returns
    the async MCPAdapter tools; use them with ainvoke on that same loop.
    """
    if target is None:
        from dataflow.mcp.server import mcp as server

        target = server
    adapter, raw = run_async(_open_and_list(target))
    _ADAPTERS.append(adapter)
    if wrap:
        return [_sync_wrap(tool) for tool in raw]
    return raw


def bound_names(tools: list[Any] | None = None) -> list[str]:
    rows = tools if tools is not None else bind_mcp_tools()
    return [str(getattr(tool, "name", "")) for tool in rows]


def build_desk(*, model: Any = None, tools: list[Any] | None = None, system: str | None = None):
    """Desk with MCP-bound tools (or the list you pass)."""
    tool_list = tools if tools is not None else bind_mcp_tools()
    return build_rag_tool_cycle(model=model, tools=tool_list, system=system)
