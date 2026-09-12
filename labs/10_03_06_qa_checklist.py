# %% [markdown]
# Run the QA checklist against the DataFlow desk.
#
# When this works, the empty path is the find, the bug is filed, the
# parked Playwright test is green, and the committed checklist has the
# path filled. This lab prints the before state from a string, then the
# committed file.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

checklist_path = root / "eval" / "qa" / "checklist.md"
bugs_path = root / "eval" / "qa" / "bugs.md"
committed_checklist = checklist_path.read_text(encoding="utf-8")
committed_bugs = bugs_path.read_text(encoding="utf-8")
print("checklist", checklist_path.as_posix())
print("bugs", bugs_path.as_posix())

BEFORE = """# DataFlow QA checklist

Every tick is a file path. An empty path is the find, not a pass.

| check | file path | status |
| --- | --- | --- |
| golden set | eval/golden.jsonl | pass |
| node tests | tests/test_nodes_dataflow.py | pass |
| eval CI | scripts/eval_ci.py | pass |
| fluent-miss cases | eval/runners/rag_metrics.py | pass |
| traces | dataflow/ops/tracer.py | pass |
| stop conditions | dataflow/graphs/durable.py | pass |
| load numbers | eval/load/replay.py | pass |
| UI paths | eval/ui/test_dataflow_chat.py | pass |
| parked write |  | gap |
"""

print("cell", "print_before")
print(BEFORE)
empty = [
    line
    for line in BEFORE.splitlines()
    if "parked write" in line and line.count("|") >= 3
]
print("empty_path_row", empty[0] if empty else None)

# %%
print("cell", "bug_entry")
print(committed_bugs)

# %%
print("cell", "run_parked_test")
result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "eval/ui/test_dataflow_chat.py::test_parked_refund_shows_parked",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(result.stdout)
print(result.stderr)
print("pytest_exit", result.returncode)

# %%
print("cell", "committed_checklist_filled")
print(committed_checklist)
print("parked_write_in_committed", "parked write" in committed_checklist)
print(
    "parked_path_filled",
    "eval/ui/test_dataflow_chat.py" in committed_checklist,
)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
checklist_path.write_text(committed_checklist, encoding="utf-8")
bugs_path.write_text(committed_bugs, encoding="utf-8")
print("restored_committed_checklist", True)
