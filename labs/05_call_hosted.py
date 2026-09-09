# %%
"""S5.2 Hosted ping. Skip without a key. Never invent tokens."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from northstar.llm import ping_hosted
import config

# %%
print("model_from_config", config.OPENAI_CHAT_MODEL or "(empty until record time)")
out = ping_hosted("ping")
print("skipped", out.get("skipped"))
print("reason", out.get("reason"))
