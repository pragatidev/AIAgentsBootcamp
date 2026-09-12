# %% [markdown]
# Read a failed DataFlow run and write the failure log.
#
# When this works, two log entries sit in harness/failure_log.md,
# each with a named bucket. The second fixture looks like a model
# limit and is re-attributed as a missing sensor.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config

failing_path = root / "harness" / "runs" / "failing_ticket.json"
lookalike_path = root / "harness" / "runs" / "model_limit_lookalike.json"
log_path = root / "harness" / "failure_log.md"
committed_log = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""

failing = json.loads(failing_path.read_text(encoding="utf-8"))
print("model", config.CHAT_MODEL)
print("failing_path", failing_path.as_posix())
print("ticket_id", failing.get("ticket_id"))
print("ticket", failing.get("ticket"))
print("note", failing.get("note"))
print("attempts_tried", failing.get("attempts_tried"))
print("refund_count", failing.get("refund_count"))
refunds = failing.get("refunds") or []
print("refund_rows", len(refunds))
for row in refunds:
    print("refund_row", row)
issue_steps = [
    step
    for step in (failing.get("steps") or [])
    if (step.get("proposal") or {}).get("tool") == "issue_refund"
]
print("issue_refund_steps", len(issue_steps))
for step in issue_steps:
    print("issue_step", step.get("n"), step.get("proposal"), step.get("result"))

# %%
print("cell", 1)
lookalike = json.loads(lookalike_path.read_text(encoding="utf-8"))
print("lookalike_path", lookalike_path.as_posix())
print("lookalike_ticket", lookalike.get("ticket"))
print("lookalike_note", lookalike.get("note"))
print("lookup_found", lookalike.get("lookup_found"))
print("issued", lookalike.get("issued"))
print("lookalike_stop", lookalike.get("stop_reason"))
for step in lookalike.get("steps") or []:
    proposal = step.get("proposal") or {}
    print(
        "lookalike_step",
        step.get("n"),
        proposal.get("tool"),
        step.get("result"),
    )
print("first_read_bucket", "real_model_limit")
print("reattribute_bucket", "missing_sensor")
print(
    "why",
    "lookup returned found="
    + str(lookalike.get("lookup_found"))
    + " issued="
    + str(lookalike.get("issued"))
    + ". A typed miss is not a model limit. A sensor on found False is the check. "
    + str(lookalike.get("note") or ""),
)

# %%
print("cell", 2)
entry_one = [
    "## T-3005 double refund",
    "",
    "ticket: " + str(failing.get("ticket_id") or "T-3005"),
    "what happened: the desk issued "
    + str(failing.get("refund_count"))
    + " refund row(s) on DF-1010 with no guide in the window",
    "bucket: missing_guide",
    "why: nothing in the window said a refund already issued on this order must not be issued again",
    "closed by:",
    "",
]
entry_two = [
    "## lookalike claimed refund on a miss",
    "",
    "ticket: " + str(lookalike.get("ticket_id") or "lookalike"),
    "what happened: the run reads like a model limit; lookup_found="
    + str(lookalike.get("lookup_found"))
    + " issued="
    + str(lookalike.get("issued")),
    "bucket: missing_sensor",
    "why: nothing compared the tool result to the reply before it reached the customer",
    "closed by:",
    "",
]
body = (
    "# Failure log\n\n"
    + "\n".join(entry_one)
    + "\n"
    + "\n".join(entry_two)
)
log_path.write_text(body, encoding="utf-8")
print("wrote", log_path.as_posix())
print(log_path.read_text(encoding="utf-8"))
print("entries", 2)
print("buckets", "missing_guide", "missing_sensor")

# %% [markdown]
# restore the committed log so the repo stays clean; Section 20 closes it

# %%
print("cell", 3)
if committed_log:
    log_path.write_text(committed_log, encoding="utf-8")
print("restored_committed_log", bool(committed_log))
