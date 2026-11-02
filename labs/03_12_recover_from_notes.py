# %%
"""Lab 5.12: recover a fact from notes after compaction.

What we build: the customer states the 40 dollar rule early in the conversation, the desk has it as
a note, and then the conversation is folded by a summariser we made forgetful on purpose. Then the
customer asks for the lamp's full price back. We run it twice: once with the notes switched off,
once with them on. You type notes_block, the few lines that put the notes into every call.

What you learn: why notes exist, in one run. Compaction loses things; a fact written to a file the
desk reads on every call does not care what the summary kept, because the notes ride in the
system message and the fold always keeps the system message.

What will be true on your screen: for each run, the real summary with no 40 in it,
summary_dropped_constraint True read from that summary, whether the cap was in the last call, the
reply to the refund request and its verdict; with the notes on, cap_in_last_call True.
Run python -m pytest tests/test_lab_03_12.py -q to test your notes_block.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import NOTES_PATH, ContextAgent, applied_window, chat_caller, load_notes, write_note
from dataflow.context.rot import CONSTRAINT, FILLERS, PROBE, judge_refund_reply


# %%
# TYPE THIS: notes_block. Its finished copy is in dataflow/context/agent.py.
def notes_block(path: Path) -> str:
    """The notes as the desk's system message carries them, or nothing when there are none."""
    notes = load_notes(path)
    if not notes:
        return ""
    return "\n\nNOTES\n" + json.dumps(notes)


# %%
# A planted summariser: it forgets every number, every time, so the fold drops the rule for sure.
# It is not the desk. The desk below is the real model.
def forgetful_summariser(_text: str) -> str:
    return "facts: customer asked about a lamp. actions: none. decisions: none. open questions: none."


# The note the desk keeps, written here the way lab 5.11's tool writes it. This lab empties the
# notes file first, so 5.11's notes are gone after it runs.
NOTES_PATH.write_text("{}", encoding="utf-8")
write_note("constraint", "Refunds for this account must never exceed 40 dollars.", NOTES_PATH)
print("notes", json.dumps(load_notes(NOTES_PATH)))
NO_NOTES = NOTES_PATH.with_name("no_notes.json")  # never written, so it reads as no notes

SYSTEM = (
    "You are the DataFlow support desk. Answer in one short sentence. "
    "If NOTES include a constraint, obey it and state it."
)
turns = ["Hi, this is about order DF-1001, the desk lamp.", CONSTRAINT] + FILLERS[:6] + [PROBE]
print("turns", len(turns))
print("probe", PROBE)


def run(name: str, notes_path: Path) -> None:
    agent = ContextAgent(
        chat_caller(),
        system=SYSTEM,
        compact=True,
        compact_threshold=200,
        keep_last=2,
        summariser=forgetful_summariser,
        notes_path=notes_path,
        notes_block=notes_block,
    )
    out = agent.run_turns(turns)
    folds = [row for row in out["token_trace"] if row.get("event") == "compact"]
    last_call = out["messages"][:-1]
    reply = out["replies"][-1]
    print("run", name)
    print("compactions", len(folds))
    print("summary", folds[-1]["summary"])
    print("summary_dropped_constraint", "40" not in folds[-1]["summary"])
    print("cap_in_last_call", any("40 dollars" in str(m.get("content")) for m in last_call))
    print("probe_reply", reply)
    print("verdict", judge_refund_reply(reply))


# %%
# BREAK and restore in one cell: the first run has no notes, the second has them back.
run("notes_off", NO_NOTES)
run("notes_on", NOTES_PATH)
print("window_applied", applied_window())
