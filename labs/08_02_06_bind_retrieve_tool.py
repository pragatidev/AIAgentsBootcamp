# %%
"""Lab 23.6: bind the FAISS retrieve tool on the DataFlow graph.

What we build: you type the retrieve tool, put it on the DataFlow desk next to the order lookup, and send
three tickets through the graph: a policy question, an order id and a thank you. Then the same policy
question on a desk whose system prompt names no tool, so the tool's description is the only routing text
the model reads, and you change that description to see what the model chooses.

What you learn: 23.5's idea made real. Retrieve is a tool the model chooses, not a step that always runs,
and it chooses on the tool's name, its arguments and its description; on this desk the system prompt also
says when to call retrieve, so the description is one of two routing texts. The scope is fixed in code:
the tool has no folder argument for the model to fill.

What will be true on your screen: the model read off the built object, then for each ticket the tool calls
with their arguments, one line per passage (source, folder, distance), the reply, and tools_fired read from
the stream: retrieve for the return question, lookup_order for DF-1002, nothing for the thank you. Then the
description-only run and its tools_fired. Then python -m pytest tests/test_lab_08_02_06.py -q passes.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.tools import tool

import config
from dataflow.graphs.rag_tool_cycle import build_rag_tool_cycle
from dataflow.tools.orders import lookup_order
from dataflow.tools.retrieve import retrieve_passages


# %%
# TYPE THIS: retrieve. The signature and docstring are given; you type the body.
# Its finished copy is dataflow/tools/retrieve.py, which the desk and every later graph bind. The
# docstring is the description the model reads.
@tool
def retrieve(question: str, k: int = 3) -> list[dict]:
    """Search the DataFlow customer policies and guides (wiki and customer facing pages) for a customer question. Returns passages with their source file."""
    return retrieve_passages(question, k=k)


# BREAK: change the docstring to
#     """Look up a DataFlow order by its id."""
# run the lab and read the description-only run's tools_fired, then python -m pytest tests/test_lab_08_02_06.py -q.
# What the model chooses is its choice on the day. git checkout -- labs/08_02_06_bind_retrieve_tool.py puts it back.


# %%
def content_text(content) -> str:
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in content).strip()
    return str(content or "").strip()


def run_ticket(graph, ticket: str) -> list[str]:
    """Stream one ticket and print what each node did. Returns the tools that fired."""
    print("ticket", ticket)
    fired: list[str] = []
    for update in graph.stream({"messages": [{"role": "user", "content": ticket}]}, stream_mode="updates"):
        for node, payload in update.items():
            for message in (payload or {}).get("messages", []):
                for call in getattr(message, "tool_calls", None) or []:
                    print(node, "tool_call", call["name"], json.dumps(call["args"]))
                if message.type == "tool":
                    fired.append(message.name)
                    rows = json.loads(message.content) if message.content.startswith(("[", "{")) else message.content
                    for row in rows if isinstance(rows, list) else [rows]:
                        if isinstance(row, dict) and "source" in row:
                            print(node, "passage", row["source"], row.get("folder"), round(float(row.get("score", 0)), 4))
                        else:
                            print(node, "result", str(row)[:200])
                elif message.type == "ai" and content_text(message.content):
                    print(node, "reply", content_text(message.content)[:300])
    print("tools_fired", fired)
    return fired


# %%
# The desk: your tool next to the order lookup, the model from config.
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
tools = [lookup_order, retrieve]
print("desk_tools", [t.name for t in tools])
print("retrieve_description", retrieve.description)
desk = build_rag_tool_cycle(model=chat, tools=tools)
policy = "Can I send back an unused lamp after twelve days?"
for ticket in (policy, "Where is order DF-1002?", "Thanks, that fixed it."):
    run_ticket(desk, ticket)


# %%
# Description only: a system prompt that names no tool, so the tool's own description is what routes.
NEUTRAL_SYSTEM = "You are the DataFlow support desk. Use a tool when one fits. After a tool result, write one short reply."
print("system", NEUTRAL_SYSTEM)
run_ticket(build_rag_tool_cycle(model=chat, tools=tools, system=NEUTRAL_SYSTEM), policy)
