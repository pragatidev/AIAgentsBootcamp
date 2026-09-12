"""DataFlow RAG tool cycle: agent, ToolNode, back to the agent.

The Section 8 cycle with retrieve on the desk's tool list. The model
chooses lookup_order, search_policy, or retrieve. Recursion cap is 10.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.runtime import Runtime

from config import get_chat_model
from dataflow.graphs.v1_triage import DeskContext
from dataflow.graphs.v2_tools import DESK_TOOLS as V2_DESK_TOOLS
from dataflow.tools.retrieve import retrieve

DESK_TOOLS = [*V2_DESK_TOOLS, retrieve]
RECURSION_LIMIT = 10

AGENT_SYSTEM = (
    "You are the DataFlow support desk. "
    "When the user names an order id like DF-1001, call lookup_order. "
    "When they ask a policy or guide question, call retrieve. "
    "Do not call search_policy when retrieve can answer. "
    "After you receive a tool result, write one short reply. "
    "Do not call a tool for thanks, chitchat, or when you already have the result."
)


class ToolCycleState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_rag_tool_cycle(*, model: Any = None, tools: list | None = None):
    tool_list = list(tools) if tools is not None else list(DESK_TOOLS)

    builder = StateGraph(ToolCycleState, context_schema=DeskContext)

    def agent_node(
        state: ToolCycleState,
        runtime: Runtime[DeskContext] | None = None,
    ) -> dict[str, list[BaseMessage]]:
        chat = model
        if chat is None and runtime is not None:
            ctx = getattr(runtime, "context", None)
            chat = getattr(ctx, "model", None) if ctx is not None else None
        if chat is None:
            chat = get_chat_model()
        bound = chat.bind_tools(tool_list)
        history = list(state.get("messages") or [])
        result = bound.invoke([SystemMessage(content=AGENT_SYSTEM), *history])
        return {"messages": [result]}

    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tool_list))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    graph = builder.compile()
    return graph.with_config({"recursion_limit": RECURSION_LIMIT})
