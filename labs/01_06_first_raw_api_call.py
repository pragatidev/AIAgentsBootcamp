# %% [markdown]
# Your first raw API call.
#
# Messages in, text out, usage printed. First the OpenAI SDK against
# Ollama's /v1 endpoint, then the same prompt through
# config.get_chat_model().

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from openai import OpenAI

import config

PROMPT = "Reply with one short sentence: what is an AI agent?"
print("prompt", PROMPT)

# %%
base = config.OLLAMA_BASE_URL.rstrip("/")
if not base.endswith("/v1"):
    base = base + "/v1"
client = OpenAI(base_url=base, api_key="ollama")
raw = client.chat.completions.create(
    model=config.CHAT_MODEL,
    messages=[{"role": "user", "content": PROMPT}],
    temperature=0,
    max_tokens=256,
    extra_body={"think": False},
)
msg = raw.choices[0].message
print("raw_model", raw.model)
print("raw_text", msg.content)
print("raw_usage", raw.usage.model_dump() if raw.usage else None)
print("raw_finish", raw.choices[0].finish_reason)

# %%
chat = config.get_chat_model(reasoning=False, num_predict=64)
lc = chat.invoke(PROMPT)
print("lc_model", getattr(chat, "model", config.CHAT_MODEL))
print("lc_text", getattr(lc, "content", lc))
print("lc_usage", getattr(lc, "usage_metadata", None))
