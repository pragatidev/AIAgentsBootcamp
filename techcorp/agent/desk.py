"""TechCorp IT desk. create_agent plus middleware."""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.messages import HumanMessage

from config import get_chat_model
from techcorp.agent.context import DeskContext
from techcorp.agent.prompts import DESK_SYSTEM_PROMPT
from techcorp.tools.accounts import grant_access, lookup_user, reset_password

DEFAULT_TOOLS = [lookup_user, reset_password, grant_access]

DEFAULT_MIDDLEWARE = [
    HumanInTheLoopMiddleware(interrupt_on={"reset_password": True}),
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
    """Build the TechCorp desk graph. Tests pass a fixture model."""
    chat = model if model is not None else get_chat_model()
    tool_list = list(tools) if tools is not None else list(DEFAULT_TOOLS)
    return create_agent(
        model=chat,
        tools=tool_list,
        system_prompt=system_prompt or DESK_SYSTEM_PROMPT,
        middleware=middleware or [],
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
    """Invoke the desk with a ticket and a DeskContext envelope."""
    payload = {"messages": [HumanMessage(content=text)]}
    ctx = DeskContext(user_id=user_id, region=region)
    config: dict[str, Any] = {}
    if thread_id:
        config["configurable"] = {"thread_id": thread_id}
    if config:
        return desk.invoke(payload, config=config, context=ctx)
    return desk.invoke(payload, context=ctx)
