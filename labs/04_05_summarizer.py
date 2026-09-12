# %% [markdown]
# Add a summarizer and watch the token count fall.
#
# Shape: facts, actions, decisions, open questions. Print token counts
# before and after each fold.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import (
    SUMMARIZE_PROMPT,
    ContextAgent,
    chat_caller,
)
from dataflow.context.rot import FILLERS

print("summary_shape", "facts, actions, decisions, open questions")
print("summary_prompt", SUMMARIZE_PROMPT)

SYSTEM = (
    "You are the DataFlow support desk. Answer in one short sentence. "
    "Keep order ids and decisions."
)
turns = [
    "Order DF-1001, the desk lamp. I want a refund later.",
    "Please email me, never call.",
] + FILLERS[:8]

# %%
agent = ContextAgent(
    chat_caller(),
    system=SYSTEM,
    compact=True,
    compact_threshold=350,
    keep_last=4,
)
out = agent.run_turns(turns)
for row in out["token_trace"]:
    if row.get("event") == "compact":
        print(
            "fold",
            "before",
            row["tokens_before"],
            "after",
            row["tokens_after"],
        )
    else:
        print("turn", row.get("turn"), "tokens", row.get("tokens"))
print("folds", sum(1 for r in out["token_trace"] if r.get("event") == "compact"))
