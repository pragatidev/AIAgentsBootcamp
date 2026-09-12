# %% [markdown]
# Bind the FAISS retrieve tool on the DataFlow graph.
#
# When this works, a return question streams a retrieve tool call and
# the passages, an order id fires lookup_order and not retrieve, and
# thanks fires no tool. Blank the description and print whether
# retrieve still fired. Restore the description.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage

from config import CHAT_MODEL
from dataflow.graphs.rag_tool_cycle import build_rag_tool_cycle
from dataflow.tools.orders import lookup_order
from dataflow.tools.policy import search_policy
from dataflow.tools.retrieve import (
    RETRIEVE_DESCRIPTION,
    build_retrieve_tool,
    retrieve,
)


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


def run_ticket(graph, text: str, label: str) -> None:
    print("ticket", label)
    print("text", text)
    tool_names: list[str] = []
    for event in graph.stream(
        {"messages": [HumanMessage(content=text)]},
        stream_mode="updates",
    ):
        print("update_keys", sorted(event.keys()))
        for node, payload in event.items():
            messages = []
            if isinstance(payload, dict):
                messages = payload.get("messages") or []
            for msg in messages:
                kind = getattr(msg, "type", type(msg).__name__)
                print("node", node, "kind", kind)
                calls = getattr(msg, "tool_calls", None) or []
                if calls:
                    print("tool_calls", calls)
                    for call in calls:
                        tool_names.append(str(call.get("name") or ""))
                name = getattr(msg, "name", None)
                if name:
                    print("tool_name", name)
                    print("tool_content", content_text(msg)[:800])
                elif content_text(msg):
                    print("content", content_text(msg)[:800])
    print("tools_fired", tool_names)
    print("---")


print("model", CHAT_MODEL)
print("retrieve_description", RETRIEVE_DESCRIPTION)
graph = build_rag_tool_cycle()

# %%
run_ticket(
    graph,
    "Can I send back an unused lamp after twelve days?",
    "return",
)

# %%
run_ticket(graph, "Where is order DF-1002?", "lookup")

# %%
run_ticket(graph, "Thanks, that fixed it.", "chitchat")

# %%
print("break_empty_description")
blank = build_retrieve_tool(description="")
print("blank_description", repr(blank.description))
broken = build_rag_tool_cycle(tools=[lookup_order, search_policy, blank])
run_ticket(
    broken,
    "Can I send back an unused lamp after twelve days?",
    "return_blank_description",
)

# %%
print("restore_description", RETRIEVE_DESCRIPTION)
restored = build_rag_tool_cycle(tools=[lookup_order, search_policy, retrieve])
run_ticket(
    restored,
    "Can I send back an unused lamp after twelve days?",
    "return_restored",
)
