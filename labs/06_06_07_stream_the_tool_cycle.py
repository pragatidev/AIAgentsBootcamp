# %%
"""Lab 15.2, second half: stream the tool cycle and watch a tool call arrive.

What we build: the tool cycle you built by hand in Lab 11.4, now streamed, so a screen could show the model
deciding to call a tool while it happens. One v2 stream asks for two lanes: messages, where the model's chunks
arrive, and updates, where each finished step arrives. Your loop prints every tool-call piece the moment it lands,
with its id, its name and its arguments exactly as they came, glues the pieces together with +, and then prints
the finished call from the agent's update and the tool's result from the tools update.

What you learn: a tool call is streamed as tool_call_chunks. The first piece carries the call's id and name; a
provider that streams arguments then sends them in pieces of text that are not valid JSON until the last one, and
qwen3:8b on Ollama sends the whole call in one piece. Either way you never act on a piece: you act on the finished
call, from the step's update, or from the pieces added together, and the two agree. On the version this course
pins (langchain-core 1.6.2), each piece shows the arguments it carried; on newer versions the event-streaming view
shows only the new part of each piece; the finished call is the same either way.

What will be true on your screen: the model line and the versions, then T-3002 streamed: each tool-call piece,
the finished call, the tool's result, the answer, the counts of pieces, text tokens and quiet chunks (chunks with
no text and no call; qwen3:8b sends a couple of hundred), then the call
added up from the pieces, the call from the update, and same_call True.
"""

from importlib.metadata import version
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langchain_core.messages import HumanMessage

import config
from dataflow.graphs.v2_tools import DESK_TOOLS, build_v2_tools

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))
print("tools", [t.name for t in DESK_TOOLS])


# %%
# TYPE THIS: stream_tool_cycle. The signature and docstring are given; you type the rest.
# The finished cycle is build_v2_tools in dataflow/graphs/v2_tools.py; this loop only watches it.
def stream_tool_cycle(graph, text):
    """Stream the cycle on messages and updates. Print each tool-call piece, then the finished call. Return both."""
    pieces, tokens, quiet = 0, 0, 0
    assembled, finished = None, None
    for part in graph.stream({"messages": [HumanMessage(content=text)]}, stream_mode=["messages", "updates"], version="v2"):
        kind, data = part["type"], part["data"]
        if kind == "messages":
            chunk, meta = data
            if chunk.type != "AIMessageChunk":
                continue
            for piece in chunk.tool_call_chunks:
                pieces += 1
                print("piece", pieces, "id", piece["id"], "name", piece["name"], "args", repr(piece["args"]))
            if chunk.tool_call_chunks:
                same_message = assembled is not None and assembled.id == chunk.id
                assembled = assembled + chunk if same_message else chunk
            elif chunk.text:
                tokens += 1
            else:
                quiet += 1
        elif "agent" in data:
            message = data["agent"]["messages"][-1]
            if message.tool_calls:
                finished = message.tool_calls
                print("finished", json.dumps([(c["name"], c["args"]) for c in finished]))
            else:
                print("answer", message.text)
        elif "tools" in data:
            result = data["tools"]["messages"][-1]
            print("tool result", result.name, result.text[:120])
    print("pieces", pieces, "text_tokens", tokens, "quiet_chunks", quiet)
    return (assembled.tool_calls if assembled is not None else None), finished


# BREAK: in the stream_mode list, delete "messages", and run. No piece is printed, pieces is 0, and nothing
# arrives while the model is working: the call shows up only when the agent's step is over, in its update.
# call_from_pieces is empty and same_call is False. Put "messages" back and run.

# %%
tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = [json.loads(line) for line in tickets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
ticket = {row["ticket_id"]: row for row in rows}["T-3002"]
print("ticket", ticket["ticket_id"], ticket["text"])

graph = build_v2_tools(model=chat)
assembled, finished = stream_tool_cycle(graph, ticket["text"])


def call_key(calls):
    return [(c["name"], c["args"], c["id"]) for c in calls or []]


print("call_from_pieces", json.dumps(call_key(assembled)))
print("call_from_update", json.dumps(call_key(finished)))
print("same_call", bool(finished) and call_key(assembled) == call_key(finished))
