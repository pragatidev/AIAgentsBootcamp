# %% [markdown]
# Calibrate the DataFlow judge against labels you wrote.
#
# When this works, ten human labels sit next to the judge from
# config, the agreement count is printed, and calibration_note.md
# names trust per kind. If they mostly agree, the note stays short.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from eval.judges.llm_judge import NOTE, judge_labelled, write_note

note_path = NOTE
committed_note = note_path.read_text(encoding="utf-8") if note_path.is_file() else ""
print("model", config.CHAT_MODEL)
print("labels", (root / "eval" / "judges" / "human_labels.jsonl").as_posix())

# %%
print("cell", "run_judge")
rows = judge_labelled()
agreed = sum(1 for row in rows if row.get("agree"))
print("side_by_side")
print("id human judge agree")
for row in rows:
    print(
        row["id"],
        row["human"],
        row["judge"],
        "yes" if row["agree"] else "no",
    )
print("agreement_count", agreed, "/", len(rows))

# %%
print("cell", "write_note")
write_note(rows=rows)
written = note_path.read_text(encoding="utf-8")
print("wrote", note_path.as_posix())
print("calibration_note")
print(written)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_note:
    note_path.write_text(committed_note, encoding="utf-8")
print("restored_committed_note", bool(committed_note))
