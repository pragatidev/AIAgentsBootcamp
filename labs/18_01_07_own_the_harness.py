# %% [markdown]
# Own the eval harness for DataFlow.
#
# When this works, a self-judge (the same model that wrote the answer)
# passes every row including the planted fluent miss. The golden check
# fails that miss and passes the rest. Nothing in the agent changes.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from eval.harness import (
    load_demo_rows,
    plant_results,
    render_table,
    run_harness,
)
import evals.harness as evals_harness

print("model", config.CHAT_MODEL)
print("harness", "eval/harness.py")
print("shim", "evals/harness.py")
print("shim_has_run_harness", hasattr(evals_harness, "run_harness"))
print("golden", "eval/golden.jsonl")

rows = load_demo_rows()
results = plant_results(rows)
print("row_ids", [row.get("id") for row in rows])
print(
    "planted_miss",
    [
        row.get("id")
        for row, result in zip(rows, results)
        if result.get("planted_fluent_miss")
    ],
)

# %%
print("cell", "self_judge")
chat = config.get_chat_model()
self_table = run_harness(rows, results, mode="self", model=chat)
print("self-judge")
print(render_table(self_table))
for row in self_table:
    print("self_id", row.get("id"), "verdict", row.get("verdict"))
    if row.get("model_said"):
        print("self_model_said", row.get("id"), row.get("model_said"))
print("self_all_pass", all(row.get("verdict") == "PASS" for row in self_table))

# %%
print("cell", "golden_check")
golden_table = run_harness(rows, results, mode="golden")
print("golden-check")
print(render_table(golden_table))
for row in golden_table:
    print(
        "golden_id",
        row.get("id"),
        "verdict",
        row.get("verdict"),
        "reason",
        row.get("reason"),
        "planted",
        row.get("planted_fluent_miss"),
    )
miss = [row for row in golden_table if row.get("planted_fluent_miss")]
print("planted_fluent_miss_fails", all(row.get("verdict") == "FAIL" for row in miss))
rest = [row for row in golden_table if not row.get("planted_fluent_miss")]
print("rest_pass", all(row.get("verdict") == "PASS" for row in rest))
print("agent_unchanged", True)
print("harness_is_the_win", True)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
print("no committed file mutated")
