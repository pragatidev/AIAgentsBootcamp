"""TechCorp IT desk. create_agent plus middleware."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    InterruptOnConfig,
    ToolCallLimitMiddleware,
)
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from config import get_chat_model
from techcorp.agent.context import DeskContext
from techcorp.agent.prompts import DESK_SYSTEM_PROMPT
from techcorp.tools.accounts import grant_access, lookup_user, reset_password

DEFAULT_TOOLS = [lookup_user, reset_password, grant_access]

# Every tool that changes something. Each one parks for a person before it runs.
WRITE_TOOLS = ("reset_password", "grant_access")


def describe_write(tool_call: dict, state: Any, runtime: Any) -> str:
    """What the reviewer reads: the tool, the employee it will act on, and what the model asked for."""
    ctx = getattr(runtime, "context", None)
    caller = getattr(ctx, "user_id", None) if ctx is not None else None
    args = tool_call.get("args") or {}
    if tool_call["name"] == "reset_password":
        # reset_password acts on the envelope's id, never on the id the model typed.
        target = caller or "nobody: the request envelope has no user id"
    else:
        target = args.get("user_id") or "nobody: no user_id in the call"
    return (
        f"{tool_call['name']} will act on {target}. "
        f"Requested by {caller or 'nobody'}. "
        f"The model asked with {json.dumps(args)}."
    )


def write_gate() -> HumanInTheLoopMiddleware:
    """Park the run before every write tool until a person decides; the description names the id the tool acts on."""
    return HumanInTheLoopMiddleware(
        interrupt_on={
            name: InterruptOnConfig(
                allowed_decisions=["approve", "edit", "reject", "respond"],
                description=describe_write,
            )
            for name in WRITE_TOOLS
        }
    )


DEFAULT_MIDDLEWARE = [
    write_gate(),
    ToolCallLimitMiddleware(run_limit=6),
]


def build_techcorp_desk(
    model=None,
    middleware=None,
    system_prompt=None,
    checkpointer=None,
    context_schema=DeskContext,
    tools=None,
):
    """Build the TechCorp desk graph. Tests pass a fixture model.

    No middleware argument gives the gated desk: DEFAULT_MIDDLEWARE, and an InMemorySaver
    when no checkpointer is passed, because a parked run needs somewhere to wait.
    An explicit list, even an empty one, is used as it is.
    """
    chat = model if model is not None else get_chat_model()
    tool_list = list(tools) if tools is not None else list(DEFAULT_TOOLS)
    if middleware is None:
        middleware = list(DEFAULT_MIDDLEWARE)
        if checkpointer is None:
            checkpointer = InMemorySaver()
    return create_agent(
        model=chat,
        tools=tool_list,
        system_prompt=system_prompt or DESK_SYSTEM_PROMPT,
        middleware=list(middleware),
        context_schema=context_schema,
        checkpointer=checkpointer,
    )


def run_ticket(
    desk,
    text: str,
    user_id: str | None = None,
    thread_id: str | None = None,
    region: str = "US",
) -> dict:
    """Invoke the desk with a ticket and a DeskContext envelope.

    Every run gets a thread id (a new one when none is passed), so a gated desk can park it.
    """
    payload = {"messages": [HumanMessage(content=text)]}
    ctx = DeskContext(user_id=user_id, region=region)
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id or f"ticket-{uuid4().hex}"}}
    return desk.invoke(payload, config=config, context=ctx)
