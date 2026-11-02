# %%
"""Lab 5.22: the long task, with the three controls together.

What we build: one customer, C-2001, and one conversation of sixty turns. The rule, refunds never
above 40 dollars, comes at turn four; then shipping, passwords, invoices and returns; then the
lamp's full price is asked for at turn sixty. The desk runs with every control from this section on:
notes for this customer, a budget with folding, just-in-time reads on the customer list through the
guard, the order lookup scoped to the customer, and the window log. Then the same task with the
controls off: no notes, no fold, the fat file pasted in, the open list. You type pass_lines, the
checks that say whether the run passed, read from the run and its log.

What you learn: how the techniques of this section hold together on a task long enough to break a
desk without them, and how you prove it held: from the log, in code, not from the last reply.

What will be true on your screen: one line per turn with its calls, its tools and its seconds; then
for the controls-on run turns 60, the largest window against the budget, stayed_under, the folds,
the reads, the notes, the verdict on the last turn, where the 40 dollar rule sat in the last window,
and other_customer_ids_in_window []; then the same block for the controls-off run, against the
window instead of the budget, and the first call that went over the window.
Run python -m pytest tests/test_lab_03_22.py -q to test your pass_lines.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from dataflow.context.agent import (
    CUSTOMER_FILES,
    ContextAgent,
    applied_window,
    context_caller,
    notes_path_for,
    read_file,
    repo_path,
)
from dataflow.context.guard import CUSTOMER_ID_RE
from dataflow.context.long_task import build_long_task
from dataflow.context.map_text import get_fat, load_map, map_header
from dataflow.context.rot import judge_refund_reply
from dataflow.context.window_log import log_path, read_log

CUSTOMER = "C-2001"
WINDOW = 4096
# BREAK: the controls-off run at the end of this file is the break, the same task with every control
# taken away. To break one control by hand, delete guard=True from the controls-on desk and run.
BUDGET = 3000
TURNS = build_long_task(60, CUSTOMER)


# %%
# TYPE THIS: pass_lines. Its finished copy is in dataflow/context/long_task.py.
def pass_lines(result: dict, rows: list[dict], limit: int, customer_id: str) -> dict:
    """The capstone's checks, read from the run's result and its window log."""
    last = rows[-1] if rows else {"messages": []}
    others = sorted(
        {cid for row in rows for m in row["messages"] for cid in CUSTOMER_ID_RE.findall(m["text"])} - {customer_id}
    )
    return {
        "turns": len(result["replies"]),
        "calls": len(rows),
        "max_window_tokens": max((row["window_tokens"] for row in rows), default=0),
        "stayed_under": all(row["window_tokens"] <= limit for row in rows),
        "compactions": sum(1 for row in result["token_trace"] if row.get("event") == "compact"),
        "verdict": judge_refund_reply(result["replies"][-1]) if result["replies"] else None,
        "cap_in_last_window": [m["source"] for m in last["messages"] if "40 dollars" in m["text"].lower()],
        "other_customer_ids_in_window": others,
    }


def show(name: str, result: dict, rows: list[dict], limit: int) -> None:
    print("run", name)
    for key, value in pass_lines(result, rows, limit, CUSTOMER).items():
        print(key, value)
    print("stop", result["stop"])
    print("reads", result["reads"])
    print("notes", json.dumps(result["notes"]))
    print("dropped_lines", result["dropped_lines"])
    print("last_reply", result["replies"][-1] if result["replies"] else None)
    if rows:
        print("last_call_sent_tokens", rows[-1]["window_tokens"], "server_read_tokens", rows[-1]["tokens"]["input"])
    print("seconds_total", round(sum(row.get("seconds", 0) for row in result["token_trace"] if row.get("turn")), 1))
    print("window_log", repo_path(log_path(name)))


SYSTEM = (
    load_map()
    + "\nWhen the customer states a rule for this account, write it with write_note under the key "
    "constraint before you answer. Obey every rule in NOTES and state it when it applies."
)

# %%
# Controls on.
notes_path_for(CUSTOMER).unlink(missing_ok=True)
log_path("lab_5_22_on").unlink(missing_ok=True)
on = ContextAgent(
    context_caller(enable_read=True, enable_notes=True, enable_orders=True, num_ctx=WINDOW),
    system=SYSTEM,
    customer_id=CUSTOMER,
    allowed=CUSTOMER_FILES,
    guard=True,
    budget=BUDGET,
    keep_last=6,
    stable_prefix=True,
    window_log=log_path("lab_5_22_on"),
    run_id="lab_5_22_on",
    map_version=map_header().get("version"),
    cap=4,
)
print("turns", len(TURNS), "window", WINDOW, "budget", BUDGET)
on_result = on.run_session(TURNS, progress_every=1)
print("window_applied", applied_window())
show("lab_5_22_on", on_result, read_log(log_path("lab_5_22_on")), BUDGET)

# %%
# Controls off: no notes, no fold, no budget, the fat file pasted in, the open list, the same window.
log_path("lab_5_22_off").unlink(missing_ok=True)
off = ContextAgent(
    context_caller(enable_read=True, enable_notes=False, num_ctx=WINDOW),
    system=SYSTEM,
    preload=get_fat(),
    reader=read_file,
    window_log=log_path("lab_5_22_off"),
    run_id="lab_5_22_off",
    cap=4,
)
off_result = off.run_session(TURNS, progress_every=1)
off_rows = read_log(log_path("lab_5_22_off"))
show("lab_5_22_off", off_result, off_rows, WINDOW)
over = next((row for row in off_rows if row["window_tokens"] > WINDOW), None)
if over:
    print("first_call_over_window", over["call_no"], "window_tokens", over["window_tokens"], "server_input_tokens", over["tokens"]["input"])
