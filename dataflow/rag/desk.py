"""The DataFlow knowledge desk on create_agent: the Section 4 agent with the retrieve tool.

One call builds it, the way Section 4 builds the TechCorp desk: a model, a tool list,
a system prompt and the request envelope. No graph is written here, so the RAG labs
that come before LangGraph run on this desk. Its limit is the reason the course then
builds the grading graph (dataflow/graphs/rag_graph.py): nothing here grades a
passage, so the desk cites every passage its tool returned, and it cannot refuse.
"""

from __future__ import annotations

import importlib
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import HumanMessage

from config import get_chat_model
from dataflow.envelope import DeskContext
from dataflow.tools.orders import lookup_order

# The module, not the tool of the same name that dataflow.tools exports.
_retrieve = importlib.import_module("dataflow.tools.retrieve")

# The desk's system prompt: one of the two routing texts the model reads. The other
# is each tool's description.
DESK_SYSTEM = (
    "You are the DataFlow support desk. "
    "When the user names an order id like DF-1001, call lookup_order. "
    "When they ask a policy or guide question, call retrieve. "
    "After you receive a tool result, write one short reply. "
    "Do not call a tool for thanks, chitchat, or when you already have the result."
)

# A run may call tools this many times. One more and the run ends with a message that says why,
# so a model that keeps calling a tool cannot spin.
TOOL_RUN_LIMIT = 4


def retrieve_tool(*, store: str | None = None, mode: str | None = None):
    """The desk's retrieve tool with the store and the search mode fixed by the deployment.

    store is "faiss" or "pgvector", mode is "dense" or "hybrid"; None reads config. Neither
    is an argument the model can fill: the model sees question and k, as on the module's tool,
    and the scope still comes from the envelope.
    """
    if store is None and mode is None:
        return _retrieve.retrieve

    @tool("retrieve", description=_retrieve.RETRIEVE_DESCRIPTION)
    def retrieve(question: str, k: int = 3, runtime: ToolRuntime[Any] = None) -> list[dict]:
        ctx = getattr(runtime, "context", None) if runtime is not None else None
        return _retrieve.retrieve_passages(question, k=k, scope=_retrieve.scope_for(ctx), store=store, mode=mode)

    return retrieve


def build_rag_desk(
    *,
    model: Any = None,
    tools: list | None = None,
    system_prompt: str | None = None,
    store: str | None = None,
    mode: str | None = None,
    middleware: list | None = None,
    checkpointer: Any = None,
):
    """create_agent with the order lookup, the retrieve tool and the DataFlow envelope. Tests pass a scripted model.

    No middleware argument gives one guard, the tool call limit (TOOL_RUN_LIMIT). An
    explicit list, even an empty one, is used as it is.
    """
    chat = model if model is not None else get_chat_model()
    tool_list = list(tools) if tools is not None else [lookup_order, retrieve_tool(store=store, mode=mode)]
    if middleware is None:
        middleware = [ToolCallLimitMiddleware(run_limit=TOOL_RUN_LIMIT, exit_behavior="end")]
    return create_agent(
        model=chat,
        tools=tool_list,
        system_prompt=system_prompt or DESK_SYSTEM,
        middleware=list(middleware),
        context_schema=DeskContext,
        checkpointer=checkpointer,
    )


def ask_desk(desk: Any, question: str, *, actor_id: str = "anon", model: Any = None) -> dict:
    """Run one question with the caller in the envelope. Returns the agent's state: its messages."""
    return desk.invoke(
        {"messages": [HumanMessage(content=question)]},
        context=DeskContext(model=model, actor_id=actor_id),
    )


def reply_text(state: dict) -> str:
    """The desk's last message as plain text: a string as it is, a list of blocks joined from their text."""
    messages = state.get("messages") or []
    content = getattr(messages[-1], "content", "") if messages else ""
    if isinstance(content, str):
        return content.strip()
    return "".join(
        str(block.get("text") or "") if isinstance(block, dict) else str(block) for block in content or []
    ).strip()
