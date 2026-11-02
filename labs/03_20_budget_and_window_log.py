# %%
"""Lab 5.20: the context budget and the window log.

What we build: a desk with a token budget it checks before every call. Over the budget, it folds the
older turns; still over, it stops with a typed stop instead of sending. Every call is written to a
window log, one row per call: each message as sent, where it came from, and its count. You type the
question the log answers that a trace cannot: where, in one call's window, a piece of text was.

What you learn: the budget as a production control, the same way a rate limit is one. The window
log as the audit of what the model saw. A stable prefix, so a note write does not change the first
message every call reuses. And an owner on the instruction file, printed from the file itself.

What will be true on your screen: the budget, the window and the map's owner and version; one line
per call with both counts, and one per fold; then stayed_under True and stop final; the log's first
and last calls by source, and rule_in_last_call naming where the 40 dollar rule sat; prefix_kept
False for the old layout and True for the stable one; and the first lines of a cost report read
from the same log.
Run python -m pytest tests/test_lab_03_20.py -q to test your where_in_window.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import ContextAgent, applied_window, chat_caller, notes_path_for, repo_path, write_note
from dataflow.context.map_text import MAP_PATH, check_map, load_map, map_header
from dataflow.context.rot import CONSTRAINT, FILLERS
from dataflow.context.window_log import log_path, read_log, sha256
from dataflow.ops.cost import render_cost_report

WINDOW = 8192
# The budget, in library tokens, checked before every call.
# BREAK: set BUDGET = 200, below the map alone, and run. No fold can get under it, so the desk stops
# on call 1 with stop budget and sends nothing. Put 900 back.
BUDGET = 900
RUN_ID = "lab_5_20"


# %%
# TYPE THIS: where_in_window. Its finished copy is in dataflow/context/window_log.py.
def where_in_window(row: dict, text: str) -> list[str]:
    """The sources of the messages in one logged call that contain text, ignoring case."""
    return [m["source"] for m in row["messages"] if text.lower() in m["text"].lower()]


# %%
header = map_header()
print("budget", BUDGET)
print("window", WINDOW)
print("map_owner", header.get("owner"))
print("map_version", header.get("version"))
print("map_problems", check_map(MAP_PATH.read_text(encoding="utf-8"), require_owner=True))

LOG = log_path(RUN_ID)
LOG.unlink(missing_ok=True)
notes = notes_path_for("C-2001")
notes.unlink(missing_ok=True)
write_note("constraint", "Refunds for this account must never exceed 40 dollars.", notes)

desk = ContextAgent(
    chat_caller(num_ctx=WINDOW),
    system=load_map(),
    customer_id="C-2001",
    budget=BUDGET,
    keep_last=4,
    stable_prefix=True,
    window_log=LOG,
    run_id=RUN_ID,
    map_version=header.get("version"),
)
turns = ["Hi, this is about order DF-1001, the desk lamp.", CONSTRAINT] + FILLERS[:18]
out = desk.run_turns(turns)
print("window_applied", applied_window())

# %%
rows = read_log(LOG)
for row in out["token_trace"]:
    if row.get("event") == "compact":
        print("fold before", row["tokens_before"], "after", row["tokens_after"])
    elif row.get("event") == "stop":
        print("stop", row["reason"], "tokens", row["tokens"], "budget", row["budget"])
    elif row.get("turn"):
        print("call", row["turn"], "tokens", row["tokens"], "server_input_tokens", row["usage"].get("input_tokens"))
print("calls", len(rows))
print("max_window_tokens", max((r["window_tokens"] for r in rows), default=0))
print("max_server_input_tokens", max((r["tokens"]["input"] or 0 for r in rows), default=0))
print("stayed_under", all(r["window_tokens"] <= BUDGET for r in rows))
print("stop", out["stop"])

# %%
print("window_log", repo_path(LOG))
if rows:
    print("first_call", [(m["source"], m["tokens"]) for m in rows[0]["messages"]])
    print("last_call", [(m["source"], m["tokens"]) for m in rows[-1]["messages"]])
    print("rule_in_last_call", where_in_window(rows[-1], "40 dollars"))
    print("map_version_in_log", sorted({r["map_version"] for r in rows}))

# %%
# The prefix: the first message, before and after a note write, in the old layout and the stable one.
check = notes_path_for("C-0520")
for stable in (False, True):
    check.unlink(missing_ok=True)
    probe = ContextAgent(chat_caller(), system=load_map(), notes_path=check, stable_prefix=stable)
    messages = [probe._first_message(), {"role": "user", "content": "hello"}]
    before = sha256(probe.window(messages)[0]["content"])
    write_note("preference", "Email only.", check)
    after = sha256(probe.window(messages)[0]["content"])
    print("stable_prefix", stable, "prefix_before", before[:12], "prefix_after", after[:12], "prefix_kept", before == after)

# %%
# The same log feeds the cost report Section 17 builds on.
report = render_cost_report(rows).splitlines()
print("\n".join(report[4:8]))
