# %% [markdown]
# Write a guide against the diagnosed DataFlow miss.
#
# When this works, the same T-3005 ticket is rerun with no guide, a
# vague guide, and the tight guide. The tight run prints one refund
# and saves harness/runs/guide_pass.json.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.agent.harness_loop import clear_refunds, load_ticket, run_desk, save_run
from dataflow.tools.refund import read_refunds
from harness.guides import VAGUE_GUIDE, load_guide

ticket = load_ticket("T-3005")
print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("ticket_text", ticket["text"])
print("agents_map", (root / "AGENTS.md").read_text(encoding="utf-8"))
print("tight_guide")
print(load_guide("no_repeat_refund.md"))
print("vague_guide", VAGUE_GUIDE)

# %%
print("cell", 1)
results = {}
for mode in ("none", "vague", "tight"):
    clear_refunds()
    print("=== guide_mode", mode)
    out = run_desk(
        ticket["text"],
        max_steps=8,
        cap_enabled=True,
        guide_mode=mode,
    )
    rows = read_refunds()
    results[mode] = {"refund_count": len(rows), "rows": rows, "out": out}
    print("stop_reason", out["stop_reason"])
    print("refund_count", len(rows))
    for row in rows:
        print("refund_row", row)
    print("steps", [(s["n"], s["proposal"]["tool"]) for s in out["steps"]])

# %%
print("cell", 2)
tight = results["tight"]
payload = {
    "ticket_id": ticket["ticket_id"],
    "ticket": ticket["text"],
    "order_id": "DF-1010",
    "guide_mode": "tight",
    "model_id": config.CHAT_MODEL,
    "refund_count": tight["refund_count"],
    "refunds": tight["rows"],
    "steps": tight["out"]["steps"],
    "stop_reason": tight["out"]["stop_reason"],
    "note": "Tight no_repeat_refund.md guide. Real model from config.get_chat_model().",
}
dest = root / "harness" / "runs" / "guide_pass.json"
committed_run = dest.read_text(encoding="utf-8") if dest.is_file() else ""
save_run(dest, payload)
print("wrote", dest.as_posix())
print("guide_pass_refund_count", tight["refund_count"])
print("none_refund_count", results["none"]["refund_count"])
print("vague_refund_count", results["vague"]["refund_count"])
print("tight_refund_count", results["tight"]["refund_count"])

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_run:
    dest.write_text(committed_run, encoding="utf-8")
print("restored_committed_run", bool(committed_run))
