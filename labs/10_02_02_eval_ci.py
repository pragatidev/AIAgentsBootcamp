# %% [markdown]
# Write the DataFlow eval CI script.
#
# When this works, eval_ci.py is green on the baseline, a Makefile
# comment is not a gate, and the workflow file is the thing that
# would stop a merge.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config

print("model", config.CHAT_MODEL)
script = root / "scripts" / "eval_ci.py"
workflow = root / ".github" / "workflows" / "eval.yml"
makefile = root / "Makefile"
print("script", script.as_posix())
print("workflow", workflow.as_posix())
print("makefile", makefile.as_posix())

# %%
print("cell", "run_green_on_baseline")
result = subprocess.run(
    [sys.executable, str(script)],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(result.stdout)
print(result.stderr)
print("eval_ci_exit", result.returncode)

# %%
print("cell", "makefile_comment_is_not_a_gate")
make_text = makefile.read_text(encoding="utf-8") if makefile.is_file() else ""
print("makefile")
print(make_text)
print("has_run_the_evals_comment", "# run the evals" in make_text)
print(
    "makefile_is_a_gate",
    False,
    "a comment nothing reads is not CI",
)

# %%
print("cell", "workflow_is_the_gate")
wf = workflow.read_text(encoding="utf-8")
print("workflow")
print(wf)
print("workflow_runs_eval_ci", "scripts/eval_ci.py --fixture" in wf)
