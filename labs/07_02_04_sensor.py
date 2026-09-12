# %% [markdown]
# Wire a DataFlow sensor that fails, then the agent self-corrects.
#
# When this works, the first run prints FAIL on a second refund, the
# next action changes, and harness/runs/sensor_self_correct.json is saved.
# Replacing the diff with a looks-good judge lets the second refund ship.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.agent.harness_loop import (
    ScriptThenModel,
    clear_refunds,
    load_ticket,
    run_desk,
    save_run,
)
from dataflow.tools.refund import read_refunds
from harness.sensors.refund_diff import refund_diff

ticket = load_ticket("T-3005")
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])
print("sensor_fn", refund_diff.__name__)

DOUBLE_SCRIPT = [
    {"tool": "lookup_order", "order_id": "DF-1010", "amount": 0.0, "reason": ""},
    {
        "tool": "issue_refund",
        "order_id": "DF-1010",
        "amount": 22.0,
        "reason": "duplicate charge",
    },
    {
        "tool": "issue_refund",
        "order_id": "DF-1010",
        "amount": 22.0,
        "reason": "duplicate charge again",
    },
]

# %%
print("cell", 1)
clear_refunds()
print("real_model_with_sensor")
real = run_desk(
    ticket["text"],
    max_steps=8,
    cap_enabled=True,
    guide_mode="none",
    sensor_enabled=True,
)
real_fail = [
    s for s in real["steps"] if (s.get("sensor") or {}).get("verdict") == "FAIL"
]
print("real_refund_count", real["refund_count"])
print("real_fail_count", len(real_fail))
for s in real["steps"]:
    print("real_step", s["n"], s["proposal"]["tool"], s.get("sensor"))

if real_fail:
    chosen = real
    print("used", "real_model_double")
else:
    print(
        "real_model_did_not_issue_a_second_refund; "
        "scripting two issue_refund proposals so the sensor can FAIL, "
        "then the real model reads that FAIL"
    )
    clear_refunds()
    hybrid = ScriptThenModel(DOUBLE_SCRIPT, config.get_chat_model())
    chosen = run_desk(
        ticket["text"],
        model=hybrid,
        max_steps=8,
        cap_enabled=True,
        guide_mode="none",
        sensor_enabled=True,
    )
    print("used", "script_then_real")

print("refund_count", chosen["refund_count"])
for row in read_refunds():
    print("refund_row", row)
fail_steps = [
    s for s in chosen["steps"] if (s.get("sensor") or {}).get("verdict") == "FAIL"
]
print("fail_count", len(fail_steps))
for s in fail_steps:
    print("FAIL", s["sensor"]["message"])
after_fail = []
seen_fail = False
for s in chosen["steps"]:
    if seen_fail:
        after_fail.append(s)
    if (s.get("sensor") or {}).get("verdict") == "FAIL":
        seen_fail = True
if after_fail:
    print("next_action_after_FAIL", after_fail[0]["proposal"]["tool"])
else:
    print("next_action_after_FAIL", "(none)")
for s in chosen["steps"]:
    print("step", s["n"], s["proposal"]["tool"], s.get("sensor"))

dest = root / "harness" / "runs" / "sensor_self_correct.json"
committed_run = dest.read_text(encoding="utf-8") if dest.is_file() else ""
save_run(
    dest,
    {
        "ticket_id": ticket["ticket_id"],
        "ticket": ticket["text"],
        "model_id": config.CHAT_MODEL,
        "refund_count": chosen["refund_count"],
        "refunds": chosen["refunds"],
        "steps": chosen["steps"],
        "stop_reason": chosen["stop_reason"],
        "note": (
            "Sensor FAIL on a second refund; the next proposal is in steps. "
            "If the live model did not double, two issue_refunds were scripted "
            "and the live model consumed the FAIL."
        ),
    },
)
print("wrote", dest.as_posix())

# %% [markdown]
# break it on purpose

# %%
print("cell", 2)

def looks_good_judge(before_rows, after_rows, order_id):
    # PLANTED MISS: a vibe check instead of the diff. Always looks good.
    chat = config.get_chat_model()
    raw = chat.invoke(
        "Does a refund on order " + str(order_id) + " look good? Two words."
    )
    print("judge_raw", getattr(raw, "content", raw))
    return {"verdict": "PASS", "message": "looks good"}


clear_refunds()
broken_model = ScriptThenModel(DOUBLE_SCRIPT, config.get_chat_model())
broken = run_desk(
    ticket["text"],
    model=broken_model,
    max_steps=6,
    cap_enabled=True,
    guide_mode="none",
    sensor_enabled=True,
    sensor_fn=looks_good_judge,
)
print("broken_refund_count", broken["refund_count"])
for row in read_refunds():
    print("broken_refund_row", row)
print("second_refund_shipped", broken["refund_count"] >= 2)
for s in broken["steps"]:
    print("broken_step", s["n"], s["proposal"]["tool"], s.get("sensor"))

# %% [markdown]
# restore

# %%
print("cell", 3)
clear_refunds()
restored_model = ScriptThenModel(DOUBLE_SCRIPT, config.get_chat_model())
restored = run_desk(
    ticket["text"],
    model=restored_model,
    max_steps=8,
    cap_enabled=True,
    guide_mode="none",
    sensor_enabled=True,
    sensor_fn=refund_diff,
)
print("restored_sensor", "refund_diff")
for s in restored["steps"]:
    if (s.get("sensor") or {}).get("verdict") == "FAIL":
        print("FAIL", s["sensor"]["message"])
print("restored_refund_count", restored["refund_count"])

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_run:
    dest.write_text(committed_run, encoding="utf-8")
print("restored_committed_run", bool(committed_run))
