"""S9: agent, ToolNode, back. Stand-in agent. No live model."""

from __future__ import annotations

import re
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from dataflow.tools.orders import lookup_order_tool


class CycleState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _last_human(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def agent(state: CycleState) -> dict[str, list[AIMessage]]:
    """Stand-in for a model. First hop calls lookup_order_tool. After the tool, stop."""
    messages = state["messages"]
    if any(isinstance(m, ToolMessage) for m in messages):
        last = next(m for m in reversed(messages) if isinstance(m, ToolMessage))
        return {"messages": [AIMessage(content=str(last.content))]}
    ticket = _last_human(messages)
    match = re.search(r"DF-\d+", ticket.upper())
    order_id = match.group(0) if match else "DF-1001"
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_order_tool",
                        "args": {"order_id": order_id},
                        "id": "call_lookup",
                    }
                ],
            )
        ]
    }


def route_after_agent(state: CycleState) -> Literal["tools", "__end__"]:
    return tools_condition(state)


def build_v2_tools():
    graph = StateGraph(CycleState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode([lookup_order_tool]))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_agent)
    graph.add_edge("tools", "agent")
    return graph.compile()
