# %% [markdown]
# Write DataFlow golden.jsonl to the twenty-ticket bar.
#
# When this works, the file prints about twenty distinct rows, the
# suite runs once on the model from config, eval/baseline.md is
# written with unique_tickets at the top, eight near-duplicates in
# memory do not raise the unique count, and two real refuse rows do.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from eval.runners.golden import (
    BASELINE,
    GOLDEN,
    load_golden,
    unique_tickets,
    write_baseline,
)

baseline_path = BASELINE
committed_baseline = (
    baseline_path.read_text(encoding="utf-8") if baseline_path.is_file() else ""
)
rows = load_golden(GOLDEN)
print("model", config.CHAT_MODEL)
print("golden", GOLDEN.as_posix())
print("row_count", len(rows))
print("unique_tickets", unique_tickets(rows))
print("refuse_rows", sum(1 for row in rows if row.get("kind") == "refuse"))

# %%
print("cell", "run_suite")
report = write_baseline()
written = baseline_path.read_text(encoding="utf-8")
print("wrote", baseline_path.as_posix())
print("baseline")
print(written)

# %%
print("cell", "planted_pad")
# Planted pad. Eight near-duplicates of existing rows, in memory only.
# eval/golden_padded.jsonl is not a file. This is the lab misbehaving
# on purpose: shuffling punctuation must not raise unique_tickets.
padded = list(rows)
for row in rows[:8]:
    clone = dict(row)
    clone["id"] = str(row.get("id")) + "-pad"
    clone["input"] = str(row.get("input") or "") + "??"
    padded.append(clone)
print("padded_row_count", len(padded))
print("unique_tickets_after_pad", unique_tickets(padded))

# %%
print("cell", "real_refuse")
extra = [
    {
        "id": "refuse-cattle",
        "kind": "refuse",
        "input": "Can I pay my DataFlow invoice in cattle?",
        "reference": None,
        "tags": ["refuse"],
    },
    {
        "id": "refuse-island",
        "kind": "refuse",
        "input": "Does the Professional plan include a private island?",
        "reference": None,
        "tags": ["refuse"],
    },
]
raised = padded + extra
print("row_count_with_real_refuse", len(raised))
print("unique_tickets_after_real_refuse", unique_tickets(raised))
print("padded_set_on_disk", False)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_baseline:
    baseline_path.write_text(committed_baseline, encoding="utf-8")
print("restored_committed_baseline", bool(committed_baseline))
