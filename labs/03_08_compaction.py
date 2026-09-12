# %% [markdown]
# Add a compaction step to the agent.
#
# Threshold, keep-last-turns, shaped summary prompt. Print the sawtooth
# of token counts across a long run.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import ContextAgent, SUMMARIZE_PROMPT, chat_caller
from dataflow.context.rot import FILLERS

SYSTEM = (
    "You are the DataFlow support desk. Answer in one short sentence. "
    "Keep order ids."
)
turns = [
    "This is about order DF-1001, the desk lamp.",
    "Please remember I want email, never a phone call.",
] + FILLERS[:10]

# %%
print("threshold", 400)
print("keep_last", 4)
print("summary_prompt", SUMMARIZE_PROMPT)
agent = ContextAgent(
    chat_caller(),
    system=SYSTEM,
    compact=True,
    compact_threshold=400,
    keep_last=4,
)
out = agent.run_turns(turns)
print("sawtooth")
for row in out["token_trace"]:
    if row.get("event") == "compact":
        print(
            "compact",
            "before",
            row["tokens_before"],
            "after",
            row["tokens_after"],
        )
    else:
        print("turn", row.get("turn"), "tokens", row.get("tokens"), "usage", row.get("usage"))
print("compactions", sum(1 for r in out["token_trace"] if r.get("event") == "compact"))
