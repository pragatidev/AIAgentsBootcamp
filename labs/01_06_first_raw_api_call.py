# %% [markdown]
# Your first raw API call.
#
# Messages in, text out, usage printed. First the OpenAI SDK against
# Ollama's /v1 endpoint with thinking switched off, then the same prompt
# through config.get_chat_model(), then the raw call again with thinking
# left on, so you can see what the hidden reasoning costs.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from openai import OpenAI

import config

PROMPT = "Reply with one short sentence: what is an AI agent?"
print("prompt", PROMPT)


def reasoning_of(message) -> str:
    """The reasoning text Ollama returns beside the answer, or '' when there is none."""
    extra = message.model_dump()
    return extra.get("reasoning") or extra.get("reasoning_content") or ""


# %%
base = config.OLLAMA_BASE_URL.rstrip("/")
if not base.endswith("/v1"):
    base = base + "/v1"
client = OpenAI(base_url=base, api_key="ollama")
# /v1 takes reasoning_effort; "none" switches thinking off. It ignores a
# "think" key, which only the native /api/chat endpoint reads.
raw = client.chat.completions.create(
    model=config.CHAT_MODEL,
    messages=[{"role": "user", "content": PROMPT}],
    temperature=0,
    max_tokens=256,
    reasoning_effort="none",
)
msg = raw.choices[0].message
print("raw_model", raw.model)
print("raw_text", msg.content)
print("raw_reasoning_chars", len(reasoning_of(msg)))
print("raw_usage", raw.usage.model_dump() if raw.usage else None)
print("raw_finish", raw.choices[0].finish_reason)

# %%
chat = config.get_chat_model(reasoning=False, num_predict=64)
lc = chat.invoke(PROMPT)
print("lc_model", getattr(chat, "model", config.CHAT_MODEL))
print("lc_text", getattr(lc, "content", lc))
print("lc_usage", getattr(lc, "usage_metadata", None))

# %%
# The same raw call with no reasoning_effort: this model thinks first.
thinking = client.chat.completions.create(
    model=config.CHAT_MODEL,
    messages=[{"role": "user", "content": PROMPT}],
    temperature=0,
    max_tokens=256,
)
thinking_msg = thinking.choices[0].message
thought = reasoning_of(thinking_msg)
print("thinking_text", thinking_msg.content)
print("thinking_reasoning_chars", len(thought))
print("thinking_reasoning_head", thought[:160].replace("\n", " "))
print("thinking_usage", thinking.usage.model_dump() if thinking.usage else None)
print("thinking_finish", thinking.choices[0].finish_reason)
