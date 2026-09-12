# %% [markdown]
# Google ADK: the same DataFlow ticket.
#
# When this works, a missing job instruction makes the agent loop
# (the lab caps it). Paste the DataFlow job from the spec and it
# stops with the policy line.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config

sys.path.insert(0, str(root / "labs" / "16_adk"))
from ticket import DATAFLOW_JOB, run as run_ticket

run_path = root / "labs" / "16_adk" / "runs" / "ticket_run.json"
committed_run = run_path.read_text(encoding="utf-8") if run_path.is_file() else ""

print("model", config.CHAT_MODEL)
print("base_url", config.OLLAMA_BASE_URL)
print("dataflow_job")
print(DATAFLOW_JOB)

# %%
print("cell", "break")
print("BREAK: missing job instruction, the agent loops (capped)")
plant = run_ticket(instruction="", max_llm_calls=4)
print("plant_fixture", plant.get("fixture"))
if plant.get("fixture"):
    print("fixture_reason", plant.get("fixture_reason"))
print("plant_event_count", plant.get("event_count"))
print("plant_has_policy_line", plant.get("has_policy_line"))
print("plant_policy_line", plant.get("policy_line"))

# %%
print("cell", "fix")
print("FIX: paste the DataFlow job from the spec")
fixed = run_ticket(instruction=DATAFLOW_JOB, max_llm_calls=8)
print("fix_fixture", fixed.get("fixture"))
if fixed.get("fixture"):
    print("fixture_reason", fixed.get("fixture_reason"))
print("fix_event_count", fixed.get("event_count"))
print("fix_has_policy_line", fixed.get("has_policy_line"))
print("fix_policy_line", fixed.get("policy_line"))
print("fix_order_row", fixed.get("order_row"))
print("fix_reply", str(fixed.get("reply") or "")[:500])

payload = {
    "model": config.CHAT_MODEL,
    "base_url": config.OLLAMA_BASE_URL,
    "plant": plant,
    "fix": fixed,
}
if plant.get("fixture") or fixed.get("fixture"):
    payload["fixture"] = True
    payload["fixture_reason"] = plant.get("fixture_reason") or fixed.get("fixture_reason")

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
print("restored_adk_run", bool(committed_run))
