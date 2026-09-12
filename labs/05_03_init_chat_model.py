# %% [markdown]
# Init a chat model from config, send messages, read usage.
#
# When this works, a reply and its usage_metadata are printed.
# The break sends the same rules as a HumanMessage instead of a
# SystemMessage and prints both replies. No claim about which is better.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

import config

tickets_path = root / "techcorp" / "data" / "tickets.jsonl"
ticket = None
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if row["ticket_id"] == "TC-1001":
        ticket = row
        break

print("model", config.CHAT_MODEL)
print("init_chat_model", "ollama:" + config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("text", ticket["text"])

# %%
model = init_chat_model("ollama:" + config.CHAT_MODEL, temperature=0)
rules = (
    "You are the TechCorp IT desk. Answer in one short paragraph. "
    "Always end with the ticket id."
)
human = HumanMessage(content=f"Ticket {ticket['ticket_id']}: {ticket['text']}")
system = SystemMessage(content=rules)

print("system_type", type(system).__name__)
print("human_type", type(human).__name__)

reply = model.invoke([system, human])
print("ai_type", type(reply).__name__)
print("system", system.content)
print("human", human.content)
print("ai", reply.content)
print("usage_metadata", reply.usage_metadata)
usage = reply.usage_metadata or {}
print("input_tokens", usage.get("input_tokens"))
print("output_tokens", usage.get("output_tokens"))
print("total_tokens", usage.get("total_tokens"))

# %%
print("BREAK: rules as HumanMessage, not SystemMessage")
as_human = HumanMessage(content=rules)
reply_human_rules = model.invoke([as_human, human])
print("system_path_reply", reply.content)
print("human_path_reply", reply_human_rules.content)
print("system_path_usage", reply.usage_metadata)
print("human_path_usage", reply_human_rules.usage_metadata)
print("printed both replies; no claim")
