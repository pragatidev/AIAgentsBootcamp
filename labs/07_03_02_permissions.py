# %% [markdown]
# Add a permission check to the DataFlow refund tool.
#
# When this works, T-3005 runs with an actor not on the list, the model
# proposes the refund, the harness blocks it, and
# harness/runs/blocked_write.json shows the refusal. Comment the check
# out and the refund goes through. Put it back and print the blocked trace.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.agent.harness_loop import clear_refunds, load_ticket, run_desk, save_run
from dataflow.tools.refund import get_refunds_path, read_refunds
from harness.permissions import ALLOWED_REFUND_ACTORS

ticket = load_ticket("T-3005")
actor = "customer-C-2010"
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])
print("actor_id", actor)
print("allowed", sorted(ALLOWED_REFUND_ACTORS))
print("actor_allowed", actor in ALLOWED_REFUND_ACTORS)

refunds_path = get_refunds_path()
clear_refunds()
print("refunds_path", refunds_path.as_posix())
print("refunds_before", read_refunds())

# %%
print("cell", 1)
blocked = run_desk(
    ticket["text"],
    max_steps=8,
    cap_enabled=True,
    guide_mode="none",
    permissions_enabled=True,
    actor_id=actor,
)
print("stop_reason", blocked["stop_reason"])
print("refund_count", blocked["refund_count"])
print("refunds_after", read_refunds())
print("refunds_unchanged", blocked["refund_count"] == 0)
proposals = [s["proposal"] for s in blocked["steps"]]
print("proposals", [(p["tool"], p.get("order_id")) for p in proposals])
blocked_steps = [s for s in blocked["steps"] if s.get("blocked")]
print("blocked_count", len(blocked_steps))
for s in blocked_steps:
    print("blocked_trace", s["blocked"]["message"])
    print("blocked_proposal", s["proposal"])

payload = {
    "ticket_id": ticket["ticket_id"],
    "ticket": ticket["text"],
    "actor_id": actor,
    "allowed": sorted(ALLOWED_REFUND_ACTORS),
    "proposal": blocked_steps[0]["proposal"] if blocked_steps else None,
    "refusal": blocked_steps[0]["blocked"] if blocked_steps else None,
    "refunds_before": [],
    "refunds_after": read_refunds(),
    "refunds_unchanged": blocked["refund_count"] == 0,
    "steps": blocked["steps"],
    "model_id": config.CHAT_MODEL,
    "note": "Real model proposed; harness blocked an actor off the list.",
}
dest = root / "harness" / "runs" / "blocked_write.json"
save_run(dest, payload)
print("wrote", dest.as_posix())

# %% [markdown]
# break it on purpose

# %%
print("cell", 2)
# PLANTED MISS: the permission check is commented out via the flag.
clear_refunds()
open_run = run_desk(
    ticket["text"],
    max_steps=8,
    cap_enabled=True,
    guide_mode="none",
    permissions_enabled=False,
    actor_id=actor,
)
print("check_commented_out", True)
print("open_refund_count", open_run["refund_count"])
for row in read_refunds():
    print("open_refund_row", row)
print("refund_went_through", open_run["refund_count"] >= 1)

# %% [markdown]
# restore

# %%
print("cell", 3)
clear_refunds()
restored = run_desk(
    ticket["text"],
    max_steps=8,
    cap_enabled=True,
    guide_mode="none",
    permissions_enabled=True,
    actor_id=actor,
)
print("check_restored", True)
print("restored_refund_count", restored["refund_count"])
print("refunds_file", read_refunds())
for s in restored["steps"]:
    if s.get("blocked"):
        print("blocked_trace", s["blocked"]["message"])
        print("blocked_tool", s["proposal"]["tool"])
        print("blocked_actor", s["blocked"]["actor_id"])
print("refunds_unchanged", restored["refund_count"] == 0)
