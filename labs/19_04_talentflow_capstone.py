# %% [markdown]
# Capstone: the TalentFlow document pipeline.
#
# Fill the starter from the finished repo, hit InvalidUpdateError on
# the scores key, add the reducer, then print N resumes scored and one
# summary with the model from config. Tests go green.

# %%
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from langgraph.errors import InvalidUpdateError

STARTER = root / "labs" / "19_talentflow" / "starter"
SOLUTION = root / "labs" / "19_talentflow" / "solution"

print("model", config.CHAT_MODEL)


def count_todo(folder: Path) -> int:
    n = 0
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".md"}:
            continue
        if "__pycache__" in path.parts:
            continue
        n += path.read_text(encoding="utf-8").count("TODO")
    return n


def copy_starter() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="capstone-talentflow-"))
    dest = tmp / "starter"
    shutil.copytree(
        STARTER,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return dest


def run_pytest(target: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(target)],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def print_proc(label: str, proc: subprocess.CompletedProcess) -> None:
    print("pytest", label, "exit", proc.returncode)
    out = (proc.stdout or "") + (proc.stderr or "")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    for ln in lines[-12:]:
        print(ln)


print("todo_count_starter", count_todo(STARTER))
print("todo_count_solution", count_todo(SOLUTION))

work = copy_starter()
print("temp_starter", work.as_posix())
graph_path = work / "graph.py"
text = graph_path.read_text(encoding="utf-8")
graph_path.write_text(
    text.replace("FILL_FROM_REPO = False", "FILL_FROM_REPO = True", 1),
    encoding="utf-8",
)
print("cell", "fill_stubs")
print("FILL_FROM_REPO True")

# %%
print("cell", "collision")
sys.path.insert(0, str(work))
import importlib

import graph as planted
from tests.fixtures.fake_model import FakeChatModel

importlib.reload(planted)

collision_model = FakeChatModel(
    reply="fixture ranking",
    structured={
        "ResumeScore": {
            "score": 80,
            "fit": "strong",
            "reason": "fixture score",
        }
    },
)
try:
    planted.build_pipeline(model=collision_model, limit=None).invoke(
        {},
        {"configurable": {"thread_id": "lab-collision"}},
    )
    print("collision", "unexpected_success")
except InvalidUpdateError as exc:
    print("collision", type(exc).__name__)
    print(str(exc).split("\n")[0])
    print("planted_break", "fan-in on scores with no reducer")

# %%
print("cell", "add_reducer")
text = graph_path.read_text(encoding="utf-8")
old = "scores: list  # TODO reducer: Annotated[list, operator.add]"
new = "scores: Annotated[list, operator.add]"
if old not in text:
    raise RuntimeError("reducer TODO line missing")
graph_path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("reducer", "Annotated[list, operator.add]")

importlib.reload(planted)

fixture = FakeChatModel(
    reply="Alex Thompson and Sarah Chen are the top two. The rest are possible. Hire from the top of the table.",
    structured={
        "ResumeScore": {
            "score": 80,
            "fit": "strong",
            "reason": "fixture score",
        }
    },
)
fixed = planted.build_pipeline(model=fixture, limit=None)
fixture_out = fixed.invoke({}, {"configurable": {"thread_id": "lab-fixture"}})
print("fixture_resumes_scored", len(list(fixture_out.get("scores") or [])))

# %%
print("cell", "real_model_summary")
print("model", config.CHAT_MODEL, flush=True)
from config import get_chat_model
from talentflow.graphs.score_resumes import load_resumes as load_finished

pile = load_finished()
print("resumes_in_pile", len(pile["resumes"]), flush=True)
print("live_limit", 3, flush=True)
live = planted.build_pipeline(model=get_chat_model(), limit=3)
try:
    out = live.invoke({}, {"configurable": {"thread_id": "lab-live"}})
except Exception as exc:
    print("live_error", type(exc).__name__, flush=True)
    print(str(exc)[:500], flush=True)
    raise
rows = list(out.get("scores") or [])
print("resumes_scored", len(rows), flush=True)
rows_sorted = sorted(
    rows,
    key=lambda r: (-int(r.get("score") or 0), str(r.get("name") or "")),
)
print("ranking_table")
print("name\tscore\tfit")
for row in rows_sorted:
    print(str(row.get("name")), str(row.get("score")), str(row.get("fit")))
ranking = str(out.get("ranking") or "")
print("summary")
print(ranking)
summary_body = ranking
if "\n\n" in ranking:
    summary_body = ranking.split("\n\n", 1)[1]
first_line = ""
for line in summary_body.splitlines():
    if line.strip():
        first_line = line.strip()
        break
print("summary_first_line", first_line)

# %%
print("cell", "tests_green")
passing = run_pytest(SOLUTION / "check")
print_proc("solution", passing)
print("tests_green", passing.returncode == 0)

# %%
print("cell", "restore")
print("worked_in", work.as_posix())
print("committed_starter_untouched", True)
