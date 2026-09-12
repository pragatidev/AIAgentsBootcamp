# %% [markdown]
# Trim and summarize a long DataFlow thread.
#
# When this works, twelve ticket turns print a token count before,
# a lower token count after, and the summary the summarize node wrote.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import AIMessage, HumanMessage

import config
from dataflow.graphs.trim import TOKEN_BUDGET, build_trim_graph, count_message_tokens

tickets_path = root / "dataflow" / "data" / "tickets.jsonl"
rows = []
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    rows.append(json.loads(line))
rows = rows[:12]

messages = []
for row in rows:
    messages.append(HumanMessage(content=row["text"]))
    messages.append(
        AIMessage(content=f"DataFlow desk noted {row['ticket_id']}.")
    )

print("turns", len(rows))
print("messages", len(messages))
print("model", config.CHAT_MODEL)
print("token_budget", TOKEN_BUDGET)
print("tokens_before", count_message_tokens(messages))

# %%
graph = build_trim_graph()
out = graph.invoke({"messages": messages})
after = out.get("messages") or []
print("tokens_after", count_message_tokens(after))
print("summary", out.get("summary"))
print("kept", len(after))
for index, msg in enumerate(after):
    role = getattr(msg, "type", type(msg).__name__)
    print("kept_role", index, role)
