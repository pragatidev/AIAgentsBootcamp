# %%
"""S5.3 Local Ollama ping. Skip if nothing is listening."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataflow.llm import ping_local
import config

# %%
print("chat_model", config.CHAT_MODEL)
print("base", config.OLLAMA_BASE_URL)
out = ping_local("ping")
print("skipped", out.get("skipped"))
print("reason", out.get("reason"))
