# %% [markdown]
# Recover a fact from notes after compaction.
#
# Compact, then ask for a fact the summary dropped. Print the summary
# and the recovered note.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import (
    ContextAgent,
    NOTES_PATH,
    chat_caller,
    load_notes,
    write_note,
)
from dataflow.context.rot import FILLERS

NOTES_PATH.write_text("{}", encoding="utf-8")
write_note(
    "constraint",
    "Refunds for this account must never exceed 40 dollars.",
    path=NOTES_PATH,
)
print("notes_before", json.dumps(load_notes(NOTES_PATH)))

SYSTEM = (
    "You are the DataFlow support desk. Answer in one short sentence. "
    "If NOTES include a constraint, obey it."
)

lossy = (
    "facts: customer asked about a lamp. "
    "actions: none. "
    "decisions: none. "
    "open questions: none."
)

# %%
agent = ContextAgent(
    chat_caller(),
    system=SYSTEM,
    compact=True,
    compact_threshold=200,
    keep_last=2,
    summariser=lambda _text: lossy,
    notes_path=NOTES_PATH,
)
turns = ["Order DF-1001, the desk lamp."] + FILLERS[:6]
out = agent.run_turns(turns)
summaries = [
    m.get("content")
    for m in out["messages"]
    if str(m.get("content") or "").startswith("SUMMARY")
]
print("summary_dropped_constraint", "40" not in lossy)
print("summary", lossy)
print("notes_after_compact", json.dumps(load_notes(NOTES_PATH)))

# %%
ask = ContextAgent(
    chat_caller(),
    system=SYSTEM,
    notes_path=NOTES_PATH,
)
probe = ask.run_turns(
    [
        "Please refund 129 dollars for the desk lamp. What cap applies?"
    ]
)
print("probe_reply", probe["replies"][0])
print("recovered_from_notes", "40" in (probe["replies"][0] or ""))
print("notes", json.dumps(load_notes(NOTES_PATH)))
