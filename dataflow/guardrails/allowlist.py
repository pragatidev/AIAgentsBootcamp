"""Allowlist at the tool port.

harness.permissions.apply_write_permission catches writes when the
harness check is on (Section 21). This allowlist catches guarded tools
for this actor even when that harness check is off. Call the harness
check first, then this one.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from harness.permissions import apply_write_permission

GUARDED_TOOLS = {"issue_refund", "decline_refund"}

_ACTOR_TABLE = {
    "reviewer-1": set(GUARDED_TOOLS),
    "reviewer-2": set(GUARDED_TOOLS),
    "desk-lead": set(GUARDED_TOOLS),
    "anon": set(),
}


def allowed_tools(actor_id: str) -> set[str]:
    """Who may call the refund tools. A missing name is a miss, not a guess."""
    return set(_ACTOR_TABLE.get(str(actor_id), set()))


class ToolNotAllowed(Exception):
    """Typed miss naming actor and tool. The model reads this, the run does not die."""

    def __init__(self, actor_id: str, tool_name: str) -> None:
        self.actor_id = str(actor_id)
        self.tool_name = str(tool_name)
        super().__init__(
            "ToolNotAllowed: actor "
            + self.actor_id
            + " may not call "
            + self.tool_name
        )


def check_tool_call(tool_name: str, actor_id: str) -> None:
    """Raise for a guarded tool this actor may not call. Return for everything else."""
    name = str(tool_name)
    if name not in GUARDED_TOOLS:
        return
    if name not in allowed_tools(actor_id):
        raise ToolNotAllowed(str(actor_id), name)


def _wrap_one(tool: Any, actor_id: str) -> Any:
    name = str(getattr(tool, "name", "") or "")
    inner = getattr(tool, "func", None)

    def guarded(*args: Any, **kwargs: Any) -> Any:
        order_id = ""
        if kwargs.get("order_id") is not None:
            order_id = str(kwargs.get("order_id"))
        apply_write_permission(name, order_id)
        try:
            check_tool_call(name, actor_id)
        except ToolNotAllowed as exc:
            return {
                "ok": False,
                "error": "ToolNotAllowed",
                "actor": exc.actor_id,
                "tool": exc.tool_name,
                "reason": str(exc),
            }
        if inner is None:
            return tool.invoke(kwargs or (args[0] if args else {}))
        return inner(*args, **kwargs)

    return StructuredTool.from_function(
        func=guarded,
        name=name,
        description=getattr(tool, "description", "") or name,
        args_schema=getattr(tool, "args_schema", None),
    )


def guard_tools(tools: list, actor_id: str) -> list:
    """Wrap each guarded tool so the check runs at the port before the body.

    A ToolNotAllowed becomes a tool message the model reads (a typed miss),
    not an exception that kills the run.
    """
    wrapped = []
    for tool in tools:
        name = str(getattr(tool, "name", "") or "")
        if name in GUARDED_TOOLS:
            wrapped.append(_wrap_one(tool, actor_id))
        else:
            wrapped.append(tool)
    return wrapped
