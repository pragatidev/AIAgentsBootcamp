# %% [markdown]
# Capstone: the research and report agent.
#
# Run the starter with the model from config. The report has no Sources
# section. Add a citation check, watch it fail on that empty-source run,
# then run the filled agent and print a sourced report.

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

STARTER = root / "labs" / "19_research" / "starter"
SOLUTION = root / "labs" / "19_research" / "solution"
QUESTION = (
    "What are the main reasons customers ask for returns or refunds, "
    "and which policy lines apply? Write a short report with sources."
)

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
    tmp = Path(tempfile.mkdtemp(prefix="capstone-research-"))
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
sys.path.insert(0, str(work))
import agent as starter_agent

# %%
print("cell", "empty_source_run")
print("model", config.CHAT_MODEL)
empty_path = work / "reports" / "empty.md"
written = starter_agent.write_report(
    QUESTION,
    dest=empty_path,
    include_sources=False,
)
text = written.read_text(encoding="utf-8")
print("report_path", written.as_posix())
print("report")
print(text)
section = starter_agent.sources_section(text)
print("sources_section")
if section is None:
    print("missing")
else:
    print(section)
print("report_has_sources", starter_agent.report_has_sources(text))

# %%
print("cell", "citation_check_fails")
cite = work / "check" / "test_citations.py"
cite.write_text(
    """from pathlib import Path
from agent import report_has_sources

REPORT = Path(__file__).resolve().parents[1] / "reports" / "empty.md"

def test_report_has_sources_section_and_a_path():
    text = REPORT.read_text(encoding="utf-8")
    assert report_has_sources(text)
""",
    encoding="utf-8",
)
failing = run_pytest(cite)
print_proc("citation_on_empty", failing)
print("citation_check_failed_on_empty_source_run", failing.returncode != 0)

# %%
print("cell", "sourced_report")
sys.path.insert(0, str(SOLUTION))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "solution_agent", SOLUTION / "agent.py"
)
solution_agent = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(solution_agent)

sourced_path = work / "reports" / "sourced.md"
sourced = solution_agent.write_report(
    QUESTION,
    dest=sourced_path,
    include_sources=True,
)
sourced_text = sourced.read_text(encoding="utf-8")
print("report_path", sourced.as_posix())
print("report")
print(sourced_text)
print("sources_section")
print(solution_agent.sources_section(sourced_text))
print("report_has_sources", solution_agent.report_has_sources(sourced_text))

cite.write_text(
    """from pathlib import Path
from agent import report_has_sources

REPORT = Path(__file__).resolve().parents[1] / "reports" / "sourced.md"

def test_report_has_sources_section_and_a_path():
    text = REPORT.read_text(encoding="utf-8")
    assert report_has_sources(text)
""",
    encoding="utf-8",
)
# sourced.md is under work/reports; the test uses report_has_sources from starter agent,
# which is the same function.
passing = run_pytest(cite)
print_proc("citation_on_sourced", passing)
print("citation_check_passed_on_sourced_report", passing.returncode == 0)

# %%
print("cell", "restore")
print("worked_in", work.as_posix())
print("committed_starter_untouched", True)
