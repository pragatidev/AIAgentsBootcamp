# %%
"""Lab 5.9: compare compacted vs uncompacted token counts.

What we build: the same fifteen turns, run twice: once with every turn kept, once with the
compaction step on. You type total_input, which adds up what every call read, including the calls
that wrote the summaries, and we compare the totals and the size of the very last call.

What you learn: where "compaction flattens the cost" is true and where it is not. The last call
stays small however long the run gets; the summaries are not free, and the total saving depends
on the threshold and on what the summariser reads.

What will be true on your screen: the plain run's total; the compacted run's desk input,
summariser input and their sum; both last calls counted twice (library and server); and the
number of folds.
Run python -m pytest tests/test_lab_03_09.py -q to test your total_input.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import ContextAgent, applied_window, chat_caller
from dataflow.context.rot import FILLERS

# BREAK: set THRESHOLD = 100000, above anything this run reaches, and run. Read compactions 0 and
# two totals that differ only by the model's own wording. Put 180 back.
THRESHOLD = 180
SYSTEM = "You are the DataFlow support desk. Answer in one short sentence."
turns = ["Order DF-1001, the desk lamp."] + FILLERS[:14]


# %%
# TYPE THIS: total_input. Its finished copy is in dataflow/context/agent.py.
def total_input(trace: list) -> dict:
    """What a run read: the desk's calls, the summariser's calls, and both together."""
    desk = 0
    summariser = 0
    for row in trace:
        if row.get("event") == "compact":
            summariser += int((row.get("summariser_usage") or {}).get("input_tokens") or 0)
        elif row.get("turn") or row.get("event") == "model":
            usage = row.get("usage") or {}
            desk += int(usage.get("input_tokens") or row.get("tokens") or 0)
    return {"desk": desk, "summariser": summariser, "total": desk + summariser}


# %%
plain = ContextAgent(chat_caller(), system=SYSTEM, compact=False).run_turns(turns)
compacted = ContextAgent(
    chat_caller(),
    system=SYSTEM,
    compact=True,
    compact_threshold=THRESHOLD,
    keep_last=4,
).run_turns(turns)
print("threshold", THRESHOLD)
print("window_applied", applied_window())

# %%
plain_total = total_input(plain["token_trace"])
comp_total = total_input(compacted["token_trace"])
print("uncompacted_total_input", plain_total["total"])
print("compacted_desk_input", comp_total["desk"])
print("summariser_input", comp_total["summariser"])
print("compacted_total_input", comp_total["total"])
for name, out in (("uncompacted", plain), ("compacted", compacted)):
    last = [row for row in out["token_trace"] if row.get("turn")][-1]
    print(name + "_last_call", "library_tokens", last["tokens"], "server_input_tokens", last["usage"].get("input_tokens"))
print("compactions", sum(1 for row in compacted["token_trace"] if row.get("event") == "compact"))
