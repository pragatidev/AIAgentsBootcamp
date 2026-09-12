# %% [markdown]
# Fat file vs map on the same task.
#
# Same ticket through both instruction files. Print token counts and
# answers side by side.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import ContextAgent, chat_caller, count_tokens
from dataflow.context.map_text import MAP, get_fat

TICKET = "What is your return window for a delivered desk lamp on order DF-1001?"
FAT = get_fat()

# %%
fat_agent = ContextAgent(chat_caller(), system=FAT, cap=1)
fat_out = fat_agent.run_turns([TICKET])
fat_tokens = count_tokens(fat_out["messages"])
print("fat_tokens", fat_tokens)
print("fat_usage", fat_out["token_trace"][0]["usage"])
print("fat_answer", fat_out["replies"][0])

# %%
map_agent = ContextAgent(chat_caller(), system=MAP, cap=1)
map_out = map_agent.run_turns([TICKET])
map_tokens = count_tokens(map_out["messages"])
print("map_tokens", map_tokens)
print("map_usage", map_out["token_trace"][0]["usage"])
print("map_answer", map_out["replies"][0])
print("token_delta", fat_tokens - map_tokens)
