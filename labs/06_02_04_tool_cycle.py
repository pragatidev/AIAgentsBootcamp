# %% [markdown]
# Add a ToolNode and tools_condition.
#
# When this works, a ticket that needs a lookup prints every message
# in order: human, ai with tool_calls, tool, ai final. Then the
# mermaid drawing shows the cycle.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage

import config
from dataflow.graphs.v2_tools import build_v2_tools

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
ticket = None
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    if row["ticket_id"] == "T-3002":
        ticket = row
        break
print("ticket_id", ticket["ticket_id"])
print("text", ticket["text"])
print("model", config.CHAT_MODEL)

# %%
graph = build_v2_tools()
out = graph.invoke({"messages": [HumanMessage(content=ticket["text"])]})


def content_text(msg) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or block))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return str(content)


print("message_count", len(out["messages"]))
for index, msg in enumerate(out["messages"]):
    kind = getattr(msg, "type", type(msg).__name__)
    print("hop", index, "kind", kind)
    name = getattr(msg, "name", None)
    if name:
        print("name", name)
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        print("tool_calls", tool_calls)
    print("content", content_text(msg))
    print("---")

# %%
print("mermaid")
print(graph.get_graph().draw_mermaid())
