# %% [markdown]
# Write the notes file and the write path.
#
# The memory tool writes named keys to dataflow/context/notes.json.
# Print the notes after each turn.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import (
    ContextAgent,
    NOTES_PATH,
    context_caller,
    load_notes,
)
from dataflow.context.map_text import MAP

NOTES_PATH.write_text("{}", encoding="utf-8")
SYSTEM = (
    MAP
    + "\nWhen the customer states a fact, call write_note. "
    "Keys: customer, order, constraint, decision."
)

# %%
agent = ContextAgent(
    context_caller(enable_read=False, enable_notes=True),
    system=SYSTEM,
    notes_path=NOTES_PATH,
    cap=6,
)
turns = [
    "I am customer C-2001. My order is DF-1001, the desk lamp.",
    "HARD CONSTRAINT: refunds for this account must never exceed 40 dollars.",
    "Please note that I want email, never a phone call.",
]
for i, ticket in enumerate(turns, start=1):
    out = agent.run(ticket)
    print("turn", i)
    print("tools", out["tool_names"])
    print("final", out["final"])
    print("notes", json.dumps(load_notes(NOTES_PATH)))
