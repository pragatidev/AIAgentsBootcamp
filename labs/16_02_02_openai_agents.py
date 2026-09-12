# %% [markdown]
# OpenAI Agents SDK: the same DataFlow ticket.
#
# When this works, the refund handoff has no confirmation and a refund
# row is written. Add a guard and the second run parks. Refund writes
# go to a temp file through DATAFLOW_REFUNDS_PATH.

# %%
from pathlib import Path
import json
import os
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.tools.refund import read_refunds

sys.path.insert(0, str(root / "labs" / "16_openai_agents"))
from ticket import run as run_ticket

run_path = root / "labs" / "16_openai_agents" / "runs" / "ticket_run.json"
committed_run = run_path.read_text(encoding="utf-8") if run_path.is_file() else ""

ledger = Path(tempfile.mkdtemp(prefix="dataflow-refunds-")) / "refunds.jsonl"
os.environ["DATAFLOW_REFUNDS_PATH"] = str(ledger)
print("model", config.CHAT_MODEL)
print("base_url", config.OLLAMA_BASE_URL)
print("refunds_path", str(ledger))

payload: dict = {
    "model": config.CHAT_MODEL,
    "base_url": config.OLLAMA_BASE_URL,
    "refunds_path": str(ledger),
}

# %%
print("cell", "break")
print("BREAK: refund handoff has no confirmation")
try:
    plant = run_ticket(guarded=False)
    print("plant_parked", plant.get("parked"))
    print("plant_final", str(plant.get("final") or "")[:400])
    print("plant_ledger", read_refunds())
    payload["plant"] = plant
    payload["plant_ledger"] = read_refunds()
except Exception as exc:
    print("BLOCKED ON OPENAI AGENTS SDK")
    print(type(exc).__name__)
    print(str(exc)[:2000])
    payload["blocked"] = True
    payload["blocked_on"] = "OPENAI AGENTS SDK"
    payload["error"] = type(exc).__name__ + ": " + str(exc)[:2000]
    payload["fixture"] = True
    payload["fixture_reason"] = str(exc)[:500]
    plant = None

# %%
print("cell", "fix")
print("FIX: add a human-approval hook so the refund parks")
if ledger.exists():
    ledger.write_text("", encoding="utf-8")
try:
    if payload.get("blocked"):
        raise RuntimeError(payload.get("error") or "blocked")
    fixed = run_ticket(guarded=True)
    print("fix_parked", fixed.get("parked"))
    print("fix_interruption_count", fixed.get("interruption_count"))
    print("fix_final", str(fixed.get("final") or "")[:400])
    print("fix_ledger", read_refunds())
    print("fix_policy_line", fixed.get("policy_line"))
    print("fix_order_row", fixed.get("order_row"))
    payload["fix"] = fixed
    payload["fix_ledger"] = read_refunds()
except Exception as exc:
    print("fix_error", type(exc).__name__)
    print(str(exc)[:2000])
    if not payload.get("blocked"):
        payload["blocked"] = True
        payload["blocked_on"] = "OPENAI AGENTS SDK"
        payload["error"] = type(exc).__name__ + ": " + str(exc)[:2000]
        payload["fixture"] = True
        payload["fixture_reason"] = str(exc)[:500]

run_path.parent.mkdir(parents=True, exist_ok=True)
run_path.write_text(
    json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
    encoding="utf-8",
)
print("wrote", run_path.as_posix())

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_run:
    run_path.write_text(committed_run, encoding="utf-8")
print("restored_ticket_run", bool(committed_run))
if ledger.exists():
    ledger.write_text("", encoding="utf-8")
    print("cleared_temp_ledger", True)
