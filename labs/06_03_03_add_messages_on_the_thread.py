# %% [markdown]
# add_messages on the DataFlow thread.
#
# When this works, two turns of one ticket print a growing message
# count after each node, then the final list with roles.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages

import config
from dataflow.graphs.messages import build_messages_graph

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
by_id = {}
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    by_id[row["ticket_id"]] = row

# Same customer, same order: T-3001 then the follow-up T-3028.
turn_ids = ["T-3001", "T-3028"]
print("turn_ticket_ids", turn_ids)
print("model", config.CHAT_MODEL)
for ticket_id in turn_ids:
    print("chosen", ticket_id, by_id[ticket_id]["text"])


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


# %%
graph = build_messages_graph()
messages = []
for turn, ticket_id in enumerate(turn_ids, start=1):
    messages = list(
        add_messages(messages, [HumanMessage(content=by_id[ticket_id]["text"])])
    )
    print("turn", turn)
    print("start_count", len(messages))
    for event in graph.stream({"messages": messages}, stream_mode="updates"):
        for node, update in event.items():
            messages = list(add_messages(messages, update.get("messages") or []))
            print("after", node, "count", len(messages))

print("final_count", len(messages))
for index, msg in enumerate(messages):
    role = getattr(msg, "type", type(msg).__name__)
    name = getattr(msg, "name", None) or ""
    print("role", role, "name", name, "content", content_text(msg))
