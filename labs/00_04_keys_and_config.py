# %% [markdown]
# Keys, config.py and the cost-free path.
#
# One call on the local model. A hosted call only when a key and a
# model id are set. Otherwise the hosted skip prints honestly.

# %%
from pathlib import Path
import os
import sys

import httpx

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config

PROMPT = "Reply with one short sentence: what is an AI agent?"

print("chat_model_id", config.CHAT_MODEL)
print("ids_live_in", "config.py")

# %%
# When nothing answers at OLLAMA_BASE_URL, say so in one line and go on to
# the hosted cell. Any other error still stops the lab with its own message.
local = config.get_local_chat_model(reasoning=False, num_predict=64)
local_ran = False
try:
    local_reply = local.invoke(PROMPT)
except (httpx.ConnectError, ConnectionError):
    print(
        f"local skipped: nothing answered at {config.OLLAMA_BASE_URL}. Is Ollama installed and running? "
        'See TROUBLESHOOTING.md, "The local model cannot be reached".'
    )
else:
    local_ran = True
    print("local_model", config.CHAT_MODEL)
    print("local_reply", getattr(local_reply, "content", local_reply))

# %%
# A provider is ready when its key and its model id are both set.
# The order is the one get_chat_model uses: OpenAI first, then Anthropic.
providers = [
    ("OPENAI", config.OPENAI_CHAT_MODEL),
    ("ANTHROPIC", config.ANTHROPIC_CHAT_MODEL),
]
keyed = [(name, model) for name, model in providers if os.environ.get(f"{name}_API_KEY", "").strip()]
hosted_id = next((model for _, model in keyed if model), "")

if hosted_id:
    hosted = config.get_chat_model()
    hosted_reply = hosted.invoke(PROMPT)
    print("hosted_model", hosted_id)
    print("hosted_reply", getattr(hosted_reply, "content", hosted_reply))
    print("ran", "hosted then local" if local_ran else "hosted, local skipped")
elif keyed:
    missing = " and ".join(f"{name}_API_KEY is set but {name}_CHAT_MODEL is empty" for name, _ in keyed)
    print(f"hosted skipped: {missing}, so there is no hosted model to call. Set the model id in .env.")
else:
    print("hosted skipped: no cloud key set")
