# %%
"""S5.4 Swap the model in config, not in the graph."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config

# %%
print("CHAT_MODEL", config.CHAT_MODEL)
print("OPENAI_CHAT_MODEL", config.OPENAI_CHAT_MODEL or "(empty)")
print("ANTHROPIC_CHAT_MODEL", config.ANTHROPIC_CHAT_MODEL or "(empty)")
print("ids_live_in", "config.py")
