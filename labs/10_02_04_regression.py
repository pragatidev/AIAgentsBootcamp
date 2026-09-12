# %% [markdown]
# Break a DataFlow metric and watch CI fail.
#
# When this works, chunk_recursive at 300 drops faithfulness, eval_ci
# exits 1 with the delta printed, restore goes green, the mirror
# mistake (--compare-to last_run.md) exits 0, and pointing back at
# baseline.md exits 1.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.tools.retrieve import reset_index
from eval.runners.golden import BASELINE, LAST_RUN

script = root / "scripts" / "eval_ci.py"
regress_path = root / "eval" / "runs" / "intentional_regress.md"
committed_regress = (
    regress_path.read_text(encoding="utf-8") if regress_path.is_file() else ""
)
committed_last = LAST_RUN.read_text(encoding="utf-8") if LAST_RUN.is_file() else ""
print("model", config.CHAT_MODEL)
print("baseline", BASELINE.as_posix())


def run_ci(extra: list[str]) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(script), *extra]
    print("cmd", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# %%
print("cell", "worse_chunker")
reset_index()
worse = run_ci(
    [
        "--chunker",
        "recursive",
        "--chunk-size",
        "300",
        "--write-run",
        str(regress_path),
    ]
)
print(worse.stdout)
print(worse.stderr)
print("worse_chunker_exit", worse.returncode)
print(
    "note",
    "a tracked metric must drop: the 300 char cut loses named facts",
)
print("wrote", regress_path.as_posix())
if regress_path.is_file():
    print("intentional_regress")
    print(regress_path.read_text(encoding="utf-8"))

# %%
print("cell", "restore_chunker")
reset_index()
print("index_reset", True)

# %%
print("cell", "mirror_mistake")
# Planted mistake. Point --compare-to at eval/last_run.md, which
# eval_ci just wrote from this run, so a number compared to itself
# never moves. Worse chunker is back in.
mirror = run_ci(
    [
        "--chunker",
        "recursive",
        "--chunk-size",
        "300",
        "--compare-to",
        str(LAST_RUN),
    ]
)
print(mirror.stdout)
print(mirror.stderr)
print("mirror_exit", mirror.returncode)

# %%
print("cell", "point_back_at_baseline")
back = run_ci(
    [
        "--chunker",
        "recursive",
        "--chunk-size",
        "300",
        "--compare-to",
        str(BASELINE),
    ]
)
print(back.stdout)
print(back.stderr)
print("baseline_compare_exit", back.returncode)
reset_index()
print("index_reset", True)

# %% [markdown]
# restore the committed copies so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed_regress:
    regress_path.write_text(committed_regress, encoding="utf-8")
if committed_last:
    LAST_RUN.write_text(committed_last, encoding="utf-8")
elif LAST_RUN.is_file():
    LAST_RUN.unlink()
print("restored_committed_regress", bool(committed_regress))
print("restored_committed_last_run", bool(committed_last))
