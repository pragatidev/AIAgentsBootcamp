# %% [markdown]
# Portfolio: the research and report agent v1.
#
# Call python -m research_agent on a shipping-delay question, print the
# first 30 lines of the report, then pytest tests/test_research_agent.py.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from research_agent.agent import PACKAGE_DIR, find_report_files

QUESTION = (
    "Why do customers complain about shipping delays, and which shipping "
    "policy lines apply? Write a short report with sources."
)

print("model", config.CHAT_MODEL)
print("entry", "python -m research_agent")
print("question", QUESTION)

print("cell", 1)
result = subprocess.run(
    [sys.executable, "-m", "research_agent", QUESTION],
    cwd=root,
    check=False,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
print("subprocess_exit", result.returncode)
if result.stdout:
    print("subprocess_stdout")
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
if result.stderr:
    print("subprocess_stderr")
    print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")

print("cell", 2)
report_path = None
for line in (result.stdout or "").splitlines():
    if line.startswith("report_path "):
        value = line[len("report_path ") :].strip()
        if value and value != "none":
            report_path = Path(value)
            break
if report_path is None:
    found = find_report_files(PACKAGE_DIR)
    shipping = [p for p in found if "shipping" in p.name.lower()]
    if shipping:
        report_path = max(shipping, key=lambda p: p.stat().st_mtime)
    elif found:
        report_path = max(found, key=lambda p: p.stat().st_mtime)

if report_path is None or not Path(report_path).is_file():
    print("The agent never wrote a report.")
else:
    path = Path(report_path)
    print("report_path", path.as_posix())
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    print("report_first_30")
    for line in lines[:30]:
        print(line)
    print("report_line_count", len(lines))

print("cell", 3)
pytest_result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_research_agent.py", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", pytest_result.returncode)
