"""S10.3 Chat state with add_messages. Both turns stay. No model."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def human_turn(state: ChatState) -> dict:
    return {"messages": [HumanMessage(content="Can I return order DF-1001?")]}


def desk_turn(state: ChatState) -> dict:
    return {"messages": [AIMessage(content="looked up desk lamp")]}


def build_chat():
    graph = StateGraph(ChatState)
    graph.add_node("human_turn", human_turn)
    graph.add_node("desk_turn", desk_turn)
    graph.add_edge(START, "human_turn")
    graph.add_edge("human_turn", "desk_turn")
    graph.add_edge("desk_turn", END)
    return graph.compile()
