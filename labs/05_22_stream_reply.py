# %% [markdown]
# Stream the TechCorp reply token by token.
#
# When this works, messages mode prints tokens on one line with
# time-to-first-token, updates mode prints one line per node, and a
# BaseCallbackHandler counts tokens on on_llm_end / on_chat_model_end.

# %%
from pathlib import Path
import json
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.callbacks import BaseCallbackHandler

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk

print("model", config.CHAT_MODEL)

tickets_path = root / "techcorp" / "data" / "tickets.jsonl"
ticket = None
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if row["ticket_id"] == "TC-1002":
        ticket = row
        break

text = (
    f"Ticket {ticket['ticket_id']} for employee {ticket['customer_id']}: "
    f"{ticket['text']}"
)
payload = {"messages": [{"role": "user", "content": text}]}
ctx = DeskContext(user_id=ticket["customer_id"])
desk = build_techcorp_desk(middleware=[])


def chunk_text(chunk) -> str:
    content = getattr(chunk, "content", None)
    if content is None and isinstance(chunk, tuple):
        content = getattr(chunk[0], "content", "")
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content or "")


# %%
print("stream_mode", "messages")
started = time.perf_counter()
first = None
print("tokens", end=" ", flush=True)
for item in desk.stream(
    payload,
    config={"configurable": {"thread_id": "lab-5-22-messages"}},
    context=ctx,
    stream_mode="messages",
):
    chunk = item[0] if isinstance(item, tuple) else item
    piece = chunk_text(chunk)
    if not piece:
        continue
    if first is None:
        first = time.perf_counter() - started
    print(piece, end="", flush=True)
print()
print("time_to_first_token", first)

# %%
print("stream_mode", "updates")
for item in desk.stream(
    payload,
    config={"configurable": {"thread_id": "lab-5-22-updates"}},
    context=ctx,
    stream_mode="updates",
):
    print("node_update", item)


class TokenCounter(BaseCallbackHandler):
    def __init__(self) -> None:
        super().__init__()
        self.tokens = 0
        self.llm_end = 0
        self.chat_model_end = 0

    def _add_from(self, response) -> None:
        llm_output = getattr(response, "llm_output", None) or {}
        token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        total = token_usage.get("total_tokens")
        if total is None:
            generations = getattr(response, "generations", None) or []
            for gen_list in generations:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    usage = getattr(msg, "usage_metadata", None) or {}
                    if usage.get("total_tokens") is not None:
                        total = (total or 0) + usage.get("total_tokens")
        if total is None:
            return
        self.tokens += int(total)

    def on_llm_end(self, response, **kwargs):
        self.llm_end += 1
        self._add_from(response)

    def on_chat_model_end(self, response, **kwargs):
        self.chat_model_end += 1
        self._add_from(response)


counter = TokenCounter()
print("BaseCallbackHandler", TokenCounter.__name__)
desk.invoke(
    payload,
    config={
        "configurable": {"thread_id": "lab-5-22-callbacks"},
        "callbacks": [counter],
    },
    context=ctx,
)
print("token_count", counter.tokens)
print("on_llm_end", counter.llm_end)
print("on_chat_model_end", counter.chat_model_end)
