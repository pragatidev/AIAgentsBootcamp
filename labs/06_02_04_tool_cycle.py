# %%
"""Lab 11.4: add a ToolNode and tools_condition.

What we build: you rebuild by hand the loop create_agent gave you in one call in Section 4: an agent node
that binds the two desk tools and asks the model, a ToolNode that runs the calls the model asked for,
tools_condition to choose between the tools and the end, the edge back from the tools to the agent, and
the cap of 10 supersteps. Then T-3002 goes through it on your model and you read every message in order.

What you learn: the agent loop is a cycle on a map. The model node returns one message; tools_condition
reads its tool calls and sends them to the tools node, or a plain answer to the end; the edge back is what
makes it a loop; add_messages keeps the whole conversation in state. Two things stop it: the model answers
without a tool call, or the recursion cap. Take the edge back away and the run ends on a tool result with
nobody to read it.

What will be true on your screen: the model line and the versions, the nodes, the drawing with the cycle,
then every message of T-3002 in order (human, ai with its tool call, tool, ai with the answer), the count,
and whether the last message is the model's answer.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

import config
from dataflow.graphs.v2_tools import AGENT_SYSTEM, DESK_TOOLS, RECURSION_LIMIT, DeskContext, ToolCycleState

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))
print("tools", [t.name for t in DESK_TOOLS], "recursion_limit", RECURSION_LIMIT)


# %%
# TYPE THIS: build_tool_cycle. The signature and docstring are given; you type the rest.
# The package's finished version is build_v2_tools in dataflow/graphs/v2_tools.py.
def build_tool_cycle(model=None):
    """agent, then tools when the model asked for one, then back to agent; capped at RECURSION_LIMIT supersteps."""
    chat_model = model if model is not None else config.get_chat_model()
    builder = StateGraph(ToolCycleState, context_schema=DeskContext)

    def agent(state: ToolCycleState) -> dict:
        bound = chat_model.bind_tools(DESK_TOOLS)
        answer = bound.invoke([SystemMessage(content=AGENT_SYSTEM), *state["messages"]])
        return {"messages": [answer]}

    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(DESK_TOOLS))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    graph = builder.compile()
    return graph.with_config({"recursion_limit": RECURSION_LIMIT})


# BREAK: delete the line builder.add_edge("tools", "agent") and run. The tool still runs, and the run ends
# on the tool's message: the last message printed is the tool result and last_is_answer is False, because
# nothing sends the result back to the model. Put it back and run.

# %%
graph = build_tool_cycle(model=chat)
print("nodes", list(graph.get_graph().nodes))
print(graph.get_graph().draw_mermaid())


# %%
def content_text(content) -> str:
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in content).strip()
    return str(content or "").strip()


tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {row["ticket_id"]: row for row in map(json.loads, tickets_path.read_text(encoding="utf-8").splitlines())}
out = graph.invoke({"messages": [HumanMessage(content=by_id["T-3002"]["text"])]})
for n, message in enumerate(out["messages"]):
    line = [str(n), message.type]
    if message.type == "ai":
        line += ["calls", json.dumps([(c["name"], c["args"]) for c in message.tool_calls])]
    if message.type == "tool":
        line += [message.name]
    print(" ".join(line), content_text(message.content)[:300])
last = out["messages"][-1]
print("message_count", len(out["messages"]))
print("last_is_answer", last.type == "ai" and not last.tool_calls)
