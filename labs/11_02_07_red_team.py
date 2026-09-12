# %% [markdown]
# Run the red-team suite in eval/.
#
# When this works, three rows block, eval_ci is green, and
# --skip-red-team with a green golden path prints FAIL and exits 1.
# The curriculum says evals/; this repo's directory is eval/.

# %%
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from eval.runners.red_team import SUITE_PATH, run_red_team

print("model", config.CHAT_MODEL)
print("red_team_path", (root / "eval" / "red_team.jsonl").as_posix())
committed_suite = SUITE_PATH.read_text(encoding="utf-8") if SUITE_PATH.is_file() else ""

handle = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
handle.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = handle.name

# %%
print("cell", "run_suite")
report = run_red_team()
print("entries")
for item in report["entries"]:
    print(item.get("id"), "blocked", item.get("blocked"), item.get("why"))
print("summary", report["summary"])

# %%
print("cell", "eval_ci_green")
green = subprocess.run(
    [sys.executable, str(root / "scripts" / "eval_ci.py"), "--fixture"],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(green.stdout)
print("eval_ci_green_exit", green.returncode)

# %%
print("cell", "skip_red_team_is_fail")
skip = subprocess.run(
    [
        sys.executable,
        str(root / "scripts" / "eval_ci.py"),
        "--fixture",
        "--skip-red-team",
    ],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(skip.stdout)
print("skip_exit", skip.returncode)
print("skip_has_fail", "red_team verdict FAIL" in skip.stdout)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_suite:
    SUITE_PATH.write_text(committed_suite, encoding="utf-8")
print("restored_suite", bool(committed_suite))
