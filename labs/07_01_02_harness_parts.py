# %% [markdown]
# Name the parts of the DataFlow loop as the harness.
#
# When this works, parts.md points at real files and the capped
# run prints STOPPED. Removing the cap lets a never-stop clerk
# retry past the limit. Put the cap back and STOPPED prints again.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.agent.harness_loop import clear_refunds, load_ticket, run_desk
from dataflow.tools.refund import get_refunds_path, read_refunds
from tests.fixtures.fake_model import FakeChatModel

parts_path = root / "harness" / "parts.md"
parts = parts_path.read_text(encoding="utf-8")
print("model", config.CHAT_MODEL)
print("parts_path", parts_path.as_posix())
print(parts)
print("heading_tools", "## Tools" in parts)
print("heading_context", "## Context policy" in parts)
print("heading_permissions", "## Permissions" in parts)
print("heading_stop", "## Stop rules" in parts)
print(
    "permissions_row",
    "harness/permissions.py" in parts or "none yet, Section 21" in parts,
)

ticket = load_ticket("T-3005")
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])

never_stop = FakeChatModel(
    structured={
        "DeskAction": {
            "tool": "lookup_order",
            "order_id": "DF-1010",
            "amount": 0.0,
            "reason": "keep looking",
        }
    }
)

# %%
print("cell", 1)
refunds_path = get_refunds_path()
clear_refunds()
print("refunds_path", refunds_path.as_posix())
print("capped_run")
capped = run_desk(
    ticket["text"],
    model=never_stop,
    max_steps=4,
    cap_enabled=True,
)
print("stop_reason", capped["stop_reason"])
print("stopped_line", capped["stopped_line"])
print("steps", len(capped["steps"]))

# %%
print("cell", 2)
print("real_model_capped")
clear_refunds()
real = run_desk(
    ticket["text"],
    max_steps=6,
    cap_enabled=True,
    guide_mode="none",
)
print("stop_reason", real["stop_reason"])
print("stopped_line", real["stopped_line"] or "(model stopped itself)")
print("refund_count", real["refund_count"])
for row in read_refunds():
    print("refund_row", row)

# %% [markdown]
# break it on purpose

# %%
print("cell", 3)
# PLANTED MISS: the step cap is removed. The never-stop clerk retries
# until a capture safety ceiling, which is not a harness stop.
runaway_model = FakeChatModel(
    structured={
        "DeskAction": {
            "tool": "lookup_order",
            "order_id": "DF-1010",
            "amount": 0.0,
            "reason": "keep looking",
        }
    }
)
clear_refunds()
runaway = run_desk(
    ticket["text"],
    model=runaway_model,
    max_steps=4,
    cap_enabled=False,
    emergency_max=10,
)
print("cap_enabled", runaway["cap_enabled"])
print("stop_reason", runaway["stop_reason"])
print("stopped_line", runaway["stopped_line"] or "(none, cap is off)")
print("steps", len(runaway["steps"]))
print("ran_past_max_steps", len(runaway["steps"]) > 4)

# %% [markdown]
# restore

# %%
print("cell", 4)
restored_model = FakeChatModel(
    structured={
        "DeskAction": {
            "tool": "lookup_order",
            "order_id": "DF-1010",
            "amount": 0.0,
            "reason": "keep looking",
        }
    }
)
clear_refunds()
restored = run_desk(
    ticket["text"],
    model=restored_model,
    max_steps=4,
    cap_enabled=True,
)
print("cap_enabled", restored["cap_enabled"])
print("stop_reason", restored["stop_reason"])
print("stopped_line", restored["stopped_line"])
print("STOPPED" in (restored["stopped_line"] or ""))
