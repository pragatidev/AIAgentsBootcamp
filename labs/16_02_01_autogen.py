# %% [markdown]
# AutoGen SupportFlow: the DataFlow ticket as a multi-agent hub.
#
# When this works, the chat hits the turn cap with no answer. Add a
# stop when lookup is done (termination on the writer's message) and
# the policy line prints.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config

sys.path.insert(0, str(root / "labs" / "16_autogen"))
from supportflow import run_sync

run_path = root / "labs" / "16_autogen" / "runs" / "supportflow_run.json"
committed_run = run_path.read_text(encoding="utf-8") if run_path.is_file() else ""

print("model", config.CHAT_MODEL)
print("base_url", config.OLLAMA_BASE_URL)

# %%
print("cell", "break")
print("BREAK: the chat hits the turn cap with no answer")
plant = run_sync(stop_on_writer=False)
print("plant_stop_reason", plant.get("stop_reason"))
print("plant_message_count", plant.get("message_count"))
print("plant_has_policy_line", plant.get("has_policy_line"))
print("plant_policy_line", plant.get("policy_line"))

# %%
print("cell", "fix")
print("FIX: stop on the writer's message after lookup")
fixed = run_sync(stop_on_writer=True)
print("fix_stop_reason", fixed.get("stop_reason"))
print("fix_message_count", fixed.get("message_count"))
print("fix_order_row", fixed.get("order_row"))
print("fix_policy_line", fixed.get("policy_line"))
print("fix_has_policy_line", fixed.get("has_policy_line"))
for row in fixed.get("messages") or []:
    if row.get("source") == "writer":
        print("writer_content", (row.get("content") or "")[:500])
        break

payload = {
    "model": config.CHAT_MODEL,
    "base_url": config.OLLAMA_BASE_URL,
    "plant": plant,
    "fix": fixed,
}
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
print("restored_supportflow_run", bool(committed_run))
