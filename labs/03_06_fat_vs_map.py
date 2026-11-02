# %%
"""Lab 5.6: fat file vs map on the same task.

What we build: one customer ticket, the return window for a delivered desk lamp, sent to two
desks that differ in one thing: one carries the fat instruction file, one carries your map. You
type run_desk, which runs one desk on one ticket and returns what it sent, what the server read
and what it answered. The window is set, so the numbers mean the same on every machine.

What you learn: the costs of a fat file, measured: the tokens it puts on every call, and what
happens when the window is smaller than the file. And that a map alone answers nothing; it needs
a read, which lab 5.14 adds.

What will be true on your screen: the window, then for each desk the library count of what it
sent, the server's count of what it read, and its answer; then map_desk_tools [] and the
difference in tokens between the two desks.
Run python -m pytest tests/test_lab_03_06.py -q to test your run_desk.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import ContextAgent, applied_window, chat_caller
from dataflow.context.map_text import get_fat, load_map

TICKET = "What is your return window for a delivered desk lamp on order DF-1001?"

# The one knob: the window both desks get, in tokens. It has to hold the fat file.
# BREAK: set WINDOW = 4096 and run. The fat desk's server count stops at the window while its
# library count stays near fifteen thousand: the server cut the start of the fat file. Read what
# the fat desk answers now. Put 16384 back.
WINDOW = 16384


# %%
# TYPE THIS: run_desk.
def run_desk(system: str, ticket: str, window: int) -> tuple[int, int | None, str]:
    """Run one desk on one ticket. Returns the library count of what it sent, the server's count, and the answer."""
    agent = ContextAgent(chat_caller(num_ctx=window), system=system)
    out = agent.run_turns([ticket])
    row = out["token_trace"][0]
    return row["tokens"], row["usage"].get("input_tokens"), out["replies"][0]


# %%
fat_library, fat_server, fat_answer = run_desk(get_fat(), TICKET, WINDOW)
print("window", WINDOW)
print("window_applied", applied_window())
print("fat_library_tokens", fat_library)
print("fat_server_input_tokens", fat_server)
print("fat_answer", fat_answer)

# %%
map_library, map_server, map_answer = run_desk(load_map(), TICKET, WINDOW)
print("map_library_tokens", map_library)
print("map_server_input_tokens", map_server)
print("map_answer", map_answer)
print("map_desk_tools", chat_caller(num_ctx=WINDOW).tool_names)
print("token_delta", fat_library - map_library)
