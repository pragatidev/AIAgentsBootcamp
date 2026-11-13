"""A person in front of every MCP tool that might change the world (Lecture 29.8).

A server's annotations are hints from whoever wrote the server. The specification says a client should
never decide tool use from the annotations of a server it does not trust, and its own defaults are
read-only false and destructive true. So needs_approval lets a tool run without a person only when two
things hold: the server is on the company's allowlist (dataflow/mcp/allowlist.json), and that server says
the tool only reads. Everything else parks.

The wait lives in the desk's checkpointer, under the thread id. The MCP server holds no session, so the
server can stop and start again between the park and the decision, and the approval still lands.
"""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig, ToolCallLimitMiddleware

from dataflow.mcp.allowlist import approved_servers
from dataflow.mcp.bind import build_desk
from dataflow.rag.desk import TOOL_RUN_LIMIT


def needs_approval(tool: Any, trusted_servers: set[str]) -> bool:
    """Park this tool unless it comes from an approved server that says it only reads."""
    mcp = (tool.metadata or {}).get("mcp") or {}
    server = mcp.get("server", {}).get("name")
    read_only = (mcp.get("tool", {}).get("annotations") or {}).get("read_only_hint") is True
    return not (server in trusted_servers and read_only)


def describe_call(tool_call: dict, state: Any, runtime: Any) -> str:
    """What the person sees when a call parks: the tool and the arguments the model filled in."""
    return f"{tool_call['name']} wants to run with {tool_call['args']}. Approve or reject."


def approval_gate(tools: list[Any], trusted_servers: set[str] | None = None) -> HumanInTheLoopMiddleware:
    """Human-in-the-loop middleware keyed on every bound tool that needs approval."""
    trusted = approved_servers() if trusted_servers is None else trusted_servers
    gated = [tool.name for tool in tools if needs_approval(tool, trusted)]
    return HumanInTheLoopMiddleware(
        interrupt_on={name: InterruptOnConfig(allowed_decisions=["approve", "reject"], description=describe_call) for name in gated}
    )


def build_gated_desk(*, model: Any, tools: list[Any], checkpointer: Any, trusted_servers: set[str] | None = None):
    """The create_agent desk with the approval gate and the desk's tool call limit."""
    middleware = [approval_gate(tools, trusted_servers), ToolCallLimitMiddleware(run_limit=TOOL_RUN_LIMIT, exit_behavior="end")]
    return build_desk(model=model, tools=tools, middleware=middleware, checkpointer=checkpointer)
