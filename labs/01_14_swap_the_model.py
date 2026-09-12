# %% [markdown]
# Swap the model with one line.
#
# The same agent function runs twice. Only the model id changes.
# The output shape stays the same. Local path uses qwen3:8b and
# llama3.2:3b.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from src.part1 import run_desk

PROMPT = "Reply with one short sentence: what is an AI agent?"


# %%
first_id = config.CHAT_MODEL
second_id = config.NO_TOOLS_MODEL
print("first_id", first_id)
print("second_id", second_id)

one = run_desk(
    config.get_local_chat_model(
        model=first_id, reasoning=False, num_predict=64
    ),
    PROMPT,
)
print("run_one_model", one["model"])
print("run_one_keys", one["keys"])
print("run_one_content", one["content"])
print("run_one_usage", one["usage"])

# %%
two = run_desk(
    config.get_local_chat_model(
        model=second_id, reasoning=False, num_predict=64
    ),
    PROMPT,
)
print("run_two_model", two["model"])
print("run_two_keys", two["keys"])
print("run_two_content", two["content"])
print("run_two_usage", two["usage"])
print("same_shape", one["keys"] == two["keys"])
print("agent_code_changed", False)
