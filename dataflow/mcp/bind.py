"""Bind DataFlow MCP tools through langchain.mcp MCPAdapter, and build the desk on them.

MCPAdapter is beta in LangChain 1.4. It infers the transport from the
target: an in-process FastMCP server, a stdio MCPConfig, a ClientGroup,
or an http URL. The tools it returns are async only. This module wraps
them so the desk's plain `invoke` still runs.

A FastMCP client's connection dies if the event loop that opened it is
closed. bind keeps the adapter connected on the long-lived loop in
runtime.py until close_mcp() runs.

The desk is the create_agent desk of dataflow/rag/desk.py with the MCP
tools in place of the local ones and a system prompt that names each
tool by the name it was bound under.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from dataflow.mcp.runtime import run_async
from dataflow.rag.desk import build_rag_desk

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
    """MCPAdapter tools have no sync invoke. Wrap so the desk's invoke works.

    The call hops onto the long-lived MCP loop so it never hits a closed loop.
    The adapter's metadata (metadata["mcp"]: the server and the annotations)
    rides along on the wrapped tool.
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
        metadata=getattr(tool, "metadata", None),
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


def mcp_desk_system(names: list[str]) -> str:
    """The desk's system prompt, naming each MCP tool by the name it was bound under.

    One server binds lookup_order; two servers bind orders_lookup_order. The
    prompt reads the names from the bound list, so it never names a tool the
    desk does not have.
    """

    def named(suffix: str) -> str | None:
        return next((name for name in names if name == suffix or name.endswith("_" + suffix)), None)

    lines = ["You are the DataFlow support desk. Your tools come from MCP servers."]
    lookup, retrieve, refund = named("lookup_order"), named("retrieve"), named("refund")
    if lookup:
        lines.append(f"When the user names an order id like DF-1001, call {lookup}.")
    if retrieve:
        lines.append(f"When they ask a policy or guide question, call {retrieve}.")
    if refund:
        lines.append(f"Call {refund} only when the user asks for a refund on a named order.")
    lines.append(
        "After you receive a tool result, write one short reply. "
        "Do not call a tool for thanks, chitchat, or when you already have the result."
    )
    return " ".join(lines)


MCP_DESK_SYSTEM = mcp_desk_system(["lookup_order", "refund"])


def build_desk(
    *,
    model: Any = None,
    tools: list[Any] | None = None,
    system: str | None = None,
    middleware: list | None = None,
    checkpointer: Any = None,
):
    """The create_agent desk (dataflow/rag/desk.py) with MCP-bound tools, or the list you pass.

    system=None names the bound tools (mcp_desk_system). middleware=None keeps the
    desk's one guard, the tool call limit; a list you pass is used as it is.
    """
    tool_list = tools if tools is not None else bind_mcp_tools()
    prompt = system or mcp_desk_system(bound_names(tool_list))
    return build_rag_desk(
        model=model,
        tools=tool_list,
        system_prompt=prompt,
        middleware=middleware,
        checkpointer=checkpointer,
    )
