# %% [markdown]
# Compare compacted vs uncompacted token counts.
#
# Same turns. Print both totals.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import ContextAgent, chat_caller
from dataflow.context.rot import FILLERS

SYSTEM = "You are the DataFlow support desk. Answer in one short sentence."
turns = ["Order DF-1001, the desk lamp."] + FILLERS[:8]


def total_input(trace: list) -> int:
    n = 0
    for row in trace:
        usage = row.get("usage") or {}
        val = usage.get("input_tokens")
        if val is None:
            val = row.get("tokens") or 0
        n += int(val or 0)
    return n


# %%
plain = ContextAgent(chat_caller(), system=SYSTEM, compact=False)
plain_out = plain.run_turns(turns)
compacted = ContextAgent(
    chat_caller(),
    system=SYSTEM,
    compact=True,
    compact_threshold=350,
    keep_last=4,
)
comp_out = compacted.run_turns(turns)
print("uncompacted_total_input", total_input(plain_out["token_trace"]))
print("compacted_total_input", total_input(comp_out["token_trace"]))
print(
    "uncompacted_last_tokens",
    plain_out["token_trace"][-1]["tokens"],
)
print(
    "compacted_last_tokens",
    [r for r in comp_out["token_trace"] if r.get("turn")][-1]["tokens"],
)
print("compactions", sum(1 for r in comp_out["token_trace"] if r.get("event") == "compact"))
