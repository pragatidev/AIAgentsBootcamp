# %% [markdown]
# Keys, config.py and the cost-free path.
#
# One call on the local model. A hosted call only when a key and a
# model id are set. Otherwise the hosted skip prints honestly.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config

PROMPT = "Reply with one short sentence: what is an AI agent?"

print("chat_model_id", config.CHAT_MODEL)
print("ids_live_in", "config.py")

# %%
local = config.get_local_chat_model(reasoning=False, num_predict=64)
local_reply = local.invoke(PROMPT)
print("local_model", config.CHAT_MODEL)
print("local_reply", getattr(local_reply, "content", local_reply))

# %%
if config.has_live_key() and (config.OPENAI_CHAT_MODEL or config.ANTHROPIC_CHAT_MODEL):
    hosted = config.get_chat_model()
    hosted_id = config.OPENAI_CHAT_MODEL or config.ANTHROPIC_CHAT_MODEL
    hosted_reply = hosted.invoke(PROMPT)
    print("hosted_model", hosted_id)
    print("hosted_reply", getattr(hosted_reply, "content", hosted_reply))
    print("ran", "hosted then local")
else:
    print("hosted skipped: no cloud key set")
