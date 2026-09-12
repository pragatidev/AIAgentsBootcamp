# %% [markdown]
# Attribute three supplied DataFlow failures.
#
# When this works, each diagnoses file prints a bucket, and the
# model-limit fixture is corrected on screen because it is a missing guide.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config

diag_dir = root / "harness" / "diagnoses"
names = [
    "silent_wrong_tool.json",
    "context_rot.json",
    "real_model_limit.json",
]
print("model", config.CHAT_MODEL)
print("diag_dir", diag_dir.as_posix())
original_texts = {name: (diag_dir / name).read_text(encoding="utf-8") for name in names}

loaded = []
for name in names:
    path = diag_dir / name
    row = json.loads(path.read_text(encoding="utf-8"))
    loaded.append((name, path, row))
    print("file", name)
    print("bucket", row.get("bucket"))
    print("summary", row.get("summary"))
    print("what_was_told", row.get("what_was_told"))
    print("what_was_checked", row.get("what_was_checked"))
    print("---")

# %%
print("cell", 1)
print("silent_wrong_tool", loaded[0][2].get("bucket"))
print("context_rot", loaded[1][2].get("bucket"))
print("real_model_limit_as_labelled", loaded[2][2].get("bucket"))
print("real_model_limit_is_wrong", True)
print("corrected_bucket", "missing_guide")
print(
    "why_correct",
    "The clerk was never told that a refund already issued must not be issued again. "
    "That is a missing guide. Model limit is the bucket you pick last.",
)

# %%
print("cell", 2)
name, path, row = loaded[2]
corrected = dict(row)
print("original_bucket", corrected.get("bucket"))
corrected["bucket"] = "missing_guide"
corrected["corrected"] = True
corrected["corrected_from"] = "real_model_limit"
path.write_text(
    json.dumps(corrected, indent=2, ensure_ascii=True) + "\n",
    encoding="utf-8",
)
print("wrote", path.as_posix())
reread = json.loads(path.read_text(encoding="utf-8"))
print("reread_bucket", reread.get("bucket"))
print("files", [p.name for p in sorted(diag_dir.glob("*.json"))])
for p in sorted(diag_dir.glob("*.json")):
    data = json.loads(p.read_text(encoding="utf-8"))
    print("final", p.name, data.get("bucket"))

# %% [markdown]
# restore the fixture so the next student gets the same exercise

# %%
print("cell", 3)
path.write_text(original_texts[name], encoding="utf-8")
print("restored", path.name, json.loads(path.read_text(encoding="utf-8")).get("bucket"))
