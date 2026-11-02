# %%
"""Lab 5.11: write the notes file and the write path.

What we build: the desk gets a notes file and one tool that writes to it, a key and a one-sentence
value. You type write_note, the write path the tool runs. Three tickets: who the customer is, a
hard refund rule, a contact preference. After each one we print every write and the whole file.
Between the second and the third we overwrite the rule on purpose, and your write_note refuses.

What you learn: the memory tool in your own code. The notes file is the only thing that carries
from one ticket to the next here, a write is an assignment, and a model can write a note that is
wrong, so a rule that matters is protected by code, not by asking nicely.

What will be true on your screen: per ticket the writes and the notes; the planted overwrite
refused with "protected key, ask a person" and the 40 dollar rule still in the file; and where the
model filed the preference on ticket three, under check_this_note, for you to read word by word.
Run python -m pytest tests/test_lab_03_11.py -q to test your write_note.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import NOTES_PATH, ContextAgent, applied_window, context_caller, load_notes, repo_path
from dataflow.context.map_text import load_map

# BREAK: set PROTECTED_KEYS = set() and run. The planted write replaces the refund rule, and the
# notes file no longer says 40 dollars. Put {"constraint"} back and run again.
PROTECTED_KEYS = {"constraint"}


# %%
# TYPE THIS: write_note. Its finished copy is in dataflow/context/agent.py.
def write_note(key: str, value: str, path: Path = NOTES_PATH) -> str:
    """Write one named fact. A protected key that already holds a value is refused and the file is left alone."""
    notes = load_notes(path)
    key = str(key)
    if key in PROTECTED_KEYS and key in notes:
        return json.dumps({"ok": False, "key": key, "reason": "protected key, ask a person"})
    notes[key] = str(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notes, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return json.dumps({"ok": True, "key": key, "notes": notes})


# %%
# This lab starts from an empty notes file. Lab 5.12 empties it again.
NOTES_PATH.write_text("{}", encoding="utf-8")
print("notes_file", repo_path(NOTES_PATH))
SYSTEM = (
    load_map()
    + "\nWhen the customer states a fact, call write_note. "
    "Keys: customer, order, constraint, preference, decision."
)
agent = ContextAgent(
    context_caller(enable_read=False, enable_notes=True),
    system=SYSTEM,
    notes_path=NOTES_PATH,
    cap=6,
    note_writer=write_note,
)
tickets = [
    "I am customer C-2001. My order is DF-1001, the desk lamp.",
    "HARD CONSTRAINT: refunds for this account must never exceed 40 dollars.",
    "Please note that I want email, never a phone call.",
]


def run_ticket(n: int) -> dict:
    out = agent.run(tickets[n - 1])
    print("ticket", n, tickets[n - 1])
    for write in out["writes"]:
        print("write", write["key"], "=", write["value"], "->", write["result"]["ok"])
    print("final", out["final"])
    print("notes", json.dumps(load_notes(NOTES_PATH)))
    return out


# %%
run_ticket(1)
run_ticket(2)
print("window_applied", applied_window())

# %%
# The planted overwrite: a direct call, not the model, so it happens the same way every run.
print("planted_write", write_note("constraint", "Customer prefers email.", NOTES_PATH))
print("notes", json.dumps(load_notes(NOTES_PATH)))

# %%
third = run_ticket(3)
for write in third["writes"]:
    print("check_this_note", write["key"], "=", write["value"])
