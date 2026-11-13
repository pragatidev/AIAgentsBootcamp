# %%
"""Lab 15.2: stream tokens, node events and a progress line from one run.

What we build: one loop that watches a whole run of the DataFlow v5 desk live. The desk is the memory desk with a
speak node that streams the model's reply and sends two progress lines of its own. You ask the graph for three
lanes at once, updates, messages and custom, with version="v2", so every piece that arrives says which lane it is
on, and your loop prints each kind its own way. The second half of this lab, 06_06_07_stream_the_tool_cycle.py,
does the same on the tool cycle and watches a tool call arrive.

What you learn: a stream is the same run seen through taps. updates says which node finished and which keys it
wrote. messages carries the model's tokens, each with the name of the node that is talking, and it also carries
the messages a node writes into state, like the customer's ticket. custom carries whatever a node sends with
get_stream_writer, here "calling the model" and "model finished". values, the fourth tap, is the whole state
after every step: right for a debugger, wrong for a chat screen.

What will be true on your screen: the model line and the versions, then T-3001's run as it happens: a line per
node with the keys it wrote, the classify tokens, the two progress lines around speak, the reply typed out token
by token, then the count of parts per lane and the reply.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.graphs.v5_stream import build_v5_stream

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: watch. The signature and docstring are given; you type the rest.
# The package has no printer; tests/test_dataflow_stream.py checks the same three lanes on the same desk.
def watch(graph, payload, config):
    """One v2 stream with three lanes: node updates, model tokens, custom progress. Returns the counts and the reply."""
    counts = {}
    reply = None
    token_node = None
    for part in graph.stream(payload, config, stream_mode=["updates", "messages", "custom"], version="v2"):
        kind, data = part["type"], part["data"]
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "messages":
            token, meta = data
            if meta["langgraph_node"] != token_node:
                if token_node:
                    print()
                token_node = meta["langgraph_node"]
                print(f"tokens {token_node} {token.type}: ", end="")
            print(token.text, end="", flush=True)
            continue
        if token_node:
            print()
            token_node = None
        if kind == "updates":
            for node, update in data.items():
                print("node", node, "wrote", sorted(update or {}))
                reply = (update or {}).get("reply", reply)
        elif kind == "custom":
            print("progress", data["progress"])
        else:
            print(kind, "keys", sorted(data))
    if token_node:
        print()
    return {"counts": counts, "reply": reply}


# BREAK: in the stream_mode list, change "messages" to "values" and run. The typing stops: no tokens line at all.
# Instead a values line arrives after every step, carrying the whole state, ticket, route, reply and the rest,
# again and again. That is the debugger's tap, not the chat screen's. Put "messages" back and run.

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = [json.loads(line) for line in tickets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
by_id = {row["ticket_id"]: row for row in rows}
ticket = by_id["T-3001"]
print("ticket", ticket["ticket_id"], ticket["text"])

graph = build_v5_stream(model=chat)
seen = watch(graph, {"ticket": ticket["text"]}, {"configurable": {"thread_id": "lab-15-2"}})
print("parts", seen["counts"])
print("reply", seen["reply"])
