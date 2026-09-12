# %% [markdown]
# Run a coding loop inside a sandbox.
#
# When this works, the agent edits fixture.py so the sandbox test
# passes, a write to ../../README.md is a typed miss, and README.md
# hashes match before and after. Restore puts the sandbox files back.

# %%
from pathlib import Path
import difflib
import hashlib
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from techcorp.harness.sandboxed_loop import (
    SANDBOX,
    run_loop,
    run_tests_in_root,
    write_under_root,
)

sandbox = SANDBOX
fixture_path = sandbox / "fixture.py"
notes_path = sandbox / "notes.md"
test_path = sandbox / "test_fixture.py"
readme_path = root / "README.md"

committed_fixture = fixture_path.read_text(encoding="utf-8")
committed_notes = notes_path.read_text(encoding="utf-8")
committed_test = test_path.read_text(encoding="utf-8")
print("model", config.CHAT_MODEL)
print("sandbox", sandbox.as_posix())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def show_diff(before: str, after: str, name: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile=name,
            tofile=name,
        )
    )


BROKEN = (
    '"""Tiny sandbox function the coding loop edits."""\n'
    "\n"
    "\n"
    "def add(a: int, b: int) -> int:\n"
    "    return a - b\n"
)

# %%
print("cell", "plant_and_loop")
fixture_path.write_text(BROKEN, encoding="utf-8")
print("planted_failing_add", "return a - b")
before_tests = run_tests_in_root(sandbox)
print("tests_before_passed", before_tests["passed"])
print("tests_before_stdout", (before_tests.get("stdout") or "")[:400])
task = (
    "fixture.py has add(a, b) returning a - b. test_add expects add(2, 3) "
    "== 5. Edit fixture.py so add returns a + b, then call run_tests."
)
print("task", task)
out = run_loop(task, root=sandbox, max_steps=8)
print("stopped", out["stopped"])
print("steps", out["steps"])
print("stopped_line", out.get("stopped_line") or "")
after_src = fixture_path.read_text(encoding="utf-8")
print("diff")
diff = show_diff(BROKEN, after_src, "fixture.py")
print(diff if diff else "(fixture.py unchanged)")
after_tests = run_tests_in_root(sandbox)
print("tests_after_passed", after_tests["passed"])
print("tests_after_stdout", (after_tests.get("stdout") or "")[:400])

# %%
print("cell", "break")
before_hash = sha256(readme_path)
print("readme_hash_before", before_hash)
miss = write_under_root(
    "../../README.md",
    "pwned by the coding-agent lab",
    root=sandbox,
)
print("extra_root_miss", miss)
print("denied", miss.get("denied"))
print("reason", miss.get("reason"))
after_hash = sha256(readme_path)
print("readme_hash_after", after_hash)
print("readme_unchanged", before_hash == after_hash)
print("cell", "fix")
print("path_check_reason", miss.get("reason"))
print("sandbox_test_passed", after_tests["passed"])

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
fixture_path.write_text(committed_fixture, encoding="utf-8")
notes_path.write_text(committed_notes, encoding="utf-8")
test_path.write_text(committed_test, encoding="utf-8")
print("restored_fixture", fixture_path.read_text(encoding="utf-8") == committed_fixture)
print("restored_notes", notes_path.read_text(encoding="utf-8") == committed_notes)
print("restored_test", test_path.read_text(encoding="utf-8") == committed_test)
