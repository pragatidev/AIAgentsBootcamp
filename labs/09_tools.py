# %%
"""S9.4 Agent, ToolNode, back. One ticket. No model."""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage, ToolMessage

from dataflow.graphs.v2_tools import build_v2_tools

# %%
graph = build_v2_tools()
out = graph.invoke(
    {"messages": [HumanMessage(content="Can I return order DF-1001?")]}
)
tool_hits = [m for m in out["messages"] if isinstance(m, ToolMessage)]
print("hops", [getattr(m, "type", type(m).__name__) for m in out["messages"]])
print("tool_calls", len(tool_hits))
if tool_hits:
    row = json.loads(str(tool_hits[0].content))
    print("found", row.get("found"))
    print("item", row.get("item"))
