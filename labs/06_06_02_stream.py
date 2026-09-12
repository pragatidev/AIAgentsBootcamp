# %% [markdown]
# Stream the same ticket three ways, then custom plus updates.
#
# values is the whole state per step. updates is the per node diary.
# messages is the tokens with the node name. custom is a line you emit.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.graphs.v5_stream import build_v5_stream

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

ticket = by_id["T-3001"]
payload = {"ticket": ticket["text"]}
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])

graph = build_v5_stream()


def content_text(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(p for p in parts if p)
    if content is None:
        return ""
    return str(content)


# %%
print("mode values")
thread_values = {"configurable": {"thread_id": "lab-12-2-values"}}
final_state = None
for step, event in enumerate(
    graph.stream(payload, thread_values, stream_mode="values"),
    start=1,
):
    keys = sorted(event.keys()) if isinstance(event, dict) else [type(event).__name__]
    print("step", step, "keys", keys)
    final_state = event
print("reply", (final_state or {}).get("reply"))

# %%
print("mode updates")
thread_updates = {"configurable": {"thread_id": "lab-12-2-updates"}}
for event in graph.stream(payload, thread_updates, stream_mode="updates"):
    if not isinstance(event, dict):
        print("node", type(event).__name__, "keys", [])
        continue
    for node, update in event.items():
        if isinstance(update, dict):
            keys = sorted(update.keys())
        else:
            keys = [type(update).__name__]
        print("node", node, "keys", keys)

# %%
print("mode messages")
thread_messages = {"configurable": {"thread_id": "lab-12-2-messages"}}
chunk_count = 0
nodes_seen = set()
for event in graph.stream(payload, thread_messages, stream_mode="messages"):
    chunk_count += 1
    message = event
    meta = {}
    if isinstance(event, tuple) and len(event) == 2:
        message, meta = event
    if isinstance(meta, dict):
        node = meta.get("langgraph_node")
        if node:
            nodes_seen.add(node)
    print(content_text(message), end="", flush=True)
print()
print("chunks", chunk_count)
print("nodes", nodes_seen)

# %%
print("mode updates+custom v2")
thread_custom = {"configurable": {"thread_id": "lab-12-2-custom"}}
for part in graph.stream(
    payload,
    thread_custom,
    stream_mode=["updates", "custom"],
    version="v2",
):
    kind = part.get("type") if isinstance(part, dict) else type(part).__name__
    data = part.get("data") if isinstance(part, dict) else part
    print("type", kind, "payload", data)
print("messages_chunks", chunk_count)
