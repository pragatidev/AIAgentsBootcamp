# %% [markdown]
# Capstone: the DataFlow RAG desk.
#
# Copy the starter to a temp folder, fill the TODO nodes from the
# finished repo, watch a planted fluent miss pass because there is no
# refuse test, add the refuse test, watch it fail, then pass the suite.
# Smoke prints green. The golden set runs with the model from config.

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

STARTER = root / "labs" / "19_dataflow" / "starter"
SOLUTION = root / "labs" / "19_dataflow" / "solution"
REFUSE_LINE = "I do not have that in the knowledge base"
COFFEE = "Do you sell coffee beans in the DataFlow shop?"
PYTEST = [sys.executable, "-m", "pytest", "-q"]

print("model", config.CHAT_MODEL)
print("starter", STARTER.as_posix())
print("solution", SOLUTION.as_posix())


def count_todo(folder: Path) -> int:
    n = 0
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".md"}:
            continue
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        n += text.count("TODO")
    return n


def copy_starter() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="capstone-dataflow-"))
    dest = tmp / "starter"
    shutil.copytree(
        STARTER,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return dest


def fill_stubs(graph_path: Path) -> None:
    text = graph_path.read_text(encoding="utf-8")
    if "FILL_FROM_REPO = False" not in text:
        raise RuntimeError("FILL_FROM_REPO flag missing")
    graph_path.write_text(
        text.replace("FILL_FROM_REPO = False", "FILL_FROM_REPO = True", 1),
        encoding="utf-8",
    )


def run_pytest(target: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    args = list(PYTEST)
    if extra:
        args.extend(extra)
    args.append(str(target))
    env = os.environ.copy()
    env["DATAFLOW_UI_MODEL"] = "fixture"
    env["PYTHONPATH"] = str(root)
    return subprocess.run(
        args,
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
print("todo_diff", count_todo(STARTER) - count_todo(SOLUTION))

work = copy_starter()
print("temp_starter", work.as_posix())
graph_path = work / "graph.py"
print("cell", "fill_stubs")
fill_stubs(graph_path)
print("FILL_FROM_REPO", "True" in graph_path.read_text(encoding="utf-8").split("FILL_FROM_REPO", 1)[1][:20])

# %%
print("cell", "suite_without_refuse_test")
first = run_pytest(work / "check")
print_proc("starter_after_fill", first)
if first.returncode != 0:
    print("starter_suite_failed_after_fill")
    print(first.stdout)
    print(first.stderr)

sys.path.insert(0, str(work))
from golden import REFUSE_LINE as GOLDEN_REFUSE
from golden import load_rows, planted_fluent, run_row

rows = load_rows(work / "golden.jsonl")
coffee = next(row for row in rows if row["id"] == "refuse-coffee")
planted = run_row(coffee, use_plant=True)
print("planted_fluent_miss")
print("id", coffee["id"])
print("input", coffee["input"])
print("reply", planted.get("reply"))
print("planted", planted.get("planted"))
print("has_refuse_line", GOLDEN_REFUSE in str(planted.get("reply") or ""))
print("suite_has_refuse_test", False)
print("planted_fluent_miss_passes_without_refuse_test", first.returncode == 0)

# %%
print("cell", "add_refuse_test_watch_it_fail")
refuse_test = work / "check" / "test_refuse.py"
refuse_test.write_text(
    """from golden import REFUSE_LINE, load_rows, run_row

def test_refuse_rows_do_not_invent_a_policy():
    rows = [row for row in load_rows() if row.get("kind") == "refuse"]
    assert rows
    for row in rows:
        out = run_row(row, use_plant=True)
        reply = str(out.get("reply") or "")
        assert REFUSE_LINE in reply, row.get("id") + " " + reply
""",
    encoding="utf-8",
)
failing = run_pytest(work / "check")
print_proc("refuse_test_on_plant", failing)
print("refuse_test_failed_on_planted_miss", failing.returncode != 0)
fail_out = (failing.stdout or "") + (failing.stderr or "")
if "AssertionError" in fail_out or failing.returncode != 0:
    print("planted_break", "fluent miss failed the refuse test")

# %%
print("cell", "refuse_on_filled_graph")
os.environ["DATAFLOW_REFUNDS_PATH"] = str(work / "refunds.jsonl")
from tests.fixtures.fake_model import FakeChatModel
import graph as filled_graph

import dataflow.graphs.rag_graph as rag_mod

_orig_retrieve = rag_mod.retrieve_passages
rag_mod.retrieve_passages = lambda *args, **kwargs: []  # type: ignore[method-assign]
try:
    out = filled_graph.run_ticket(
        COFFEE,
        model=FakeChatModel(route="policy"),
        thread_id="lab-refuse",
    )
    reply = str(out.get("reply") or out.get("answer") or "")
    print("filled_graph_coffee_reply")
    print(reply)
    print("filled_graph_refused", REFUSE_LINE in reply)
finally:
    rag_mod.retrieve_passages = _orig_retrieve

refuse_test.write_text(
    """from golden import REFUSE_LINE, load_rows, run_row
from tests.fixtures.fake_model import FakeChatModel
import graph as desk
import dataflow.graphs.rag_graph as rag_mod

def test_refuse_rows_do_not_invent_a_policy(monkeypatch):
    monkeypatch.setattr(rag_mod, "retrieve_passages", lambda *a, **k: [])
    rows = [row for row in load_rows() if row.get("kind") == "refuse"]
    assert rows
    model = FakeChatModel(route="policy")
    graph = desk.build_desk(model=model)
    for row in rows:
        out = run_row(row, graph=graph, use_plant=False, thread_id="t-" + str(row.get("id")))
        reply = str(out.get("reply") or out.get("answer") or "")
        assert REFUSE_LINE in reply, row.get("id") + " " + reply
""",
    encoding="utf-8",
)
passing = run_pytest(work / "check")
print_proc("suite_with_refuse_test", passing)
print("suite_passed_after_refuse_fix", passing.returncode == 0)

# %%
print("cell", "smoke_green")
os.environ["DATAFLOW_UI_MODEL"] = "fixture"
sys.path.insert(0, str(work))
import smoke as starter_smoke

smoke_code = starter_smoke.run_smoke_in_process()
print("smoke_exit", smoke_code)

# %%
print("cell", "golden_run_real_model")
print("model", config.CHAT_MODEL)
from config import get_chat_model

real_graph = filled_graph.build_desk(model=get_chat_model())
for row in rows:
    kind = str(row.get("kind") or "")
    ticket = str(row.get("input") or "")
    try:
        scored = filled_graph.run_ticket(
            ticket,
            model=get_chat_model(),
            thread_id="golden-" + str(row.get("id")),
        )
    except Exception as exc:
        print("golden_row", row.get("id"), "ERROR", type(exc).__name__)
        print(str(exc).split("\n")[0])
        continue
    text = str(scored.get("reply") or scored.get("answer") or "")
    snippet = " ".join(text.split())[:180]
    print(
        "golden_row",
        row.get("id"),
        kind,
        "parked",
        bool(scored.get("parked")),
        "refused",
        REFUSE_LINE in text,
    )
    print("reply", snippet)

# %%
print("cell", "restore")
print("worked_in", work.as_posix())
print("committed_starter_untouched", True)
print("DATAFLOW_REFUNDS_PATH", os.environ.get("DATAFLOW_REFUNDS_PATH"))
