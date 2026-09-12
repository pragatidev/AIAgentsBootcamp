# %%
"""S8. Official hello graph. No model. Compile is required."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

# %%
class HelloState(TypedDict, total=False):
    text: str


def greet(state: HelloState) -> dict:
    return {"text": "hello " + state.get("text", "world")}


# %%
builder = StateGraph(HelloState)
builder.add_node("greet", greet)
builder.add_edge(START, "greet")
builder.add_edge("greet", END)
graph = builder.compile()

# %%
out = graph.invoke({"text": "dataflow"})
print("hello_text", out.get("text"))
print("nodes", sorted(graph.get_graph().nodes))
print("mermaid")
print(graph.get_graph().draw_mermaid())
