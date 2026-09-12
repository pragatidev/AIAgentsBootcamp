# %% [markdown]
# Return a typed miss and test both paths.
#
# When this works, a known id resets, an unknown id is a miss, and
# pytest tests/test_techcorp_tools.py is green. The break plants
# reset_password_inventing, which returns a password for any id, and
# the unknown_user test goes red.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from techcorp.tools.accounts import dummy_runtime, reset_password

known = reset_password.func("E-4101", runtime=dummy_runtime())
unknown = reset_password.func("E-9999", runtime=dummy_runtime())
print("known", known)
print("unknown", unknown)

# %%
proc = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_techcorp_tools.py",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=root,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("pytest_stdout")
print(proc.stdout)
print("pytest_stderr")
print(proc.stderr)
print("exit_code", proc.returncode)

# %%
print("BREAK: reset_password_inventing returns a password for any id")


def reset_password_inventing(user_id: str, runtime=None) -> dict:
    return {
        "found": True,
        "user_id": user_id,
        "temporary_password": "invented01",
        "expires_in_hours": 24,
    }


print("inventing_unknown", reset_password_inventing("E-9999"))

plant = root / "_plant_inventing.py"
plant.write_text(
    "def pytest_runtest_setup(item):\n"
    "    from techcorp.tools.accounts import reset_password\n"
    "    def reset_password_inventing(user_id, runtime=None):\n"
    "        return {\n"
    '            "found": True,\n'
    '            "user_id": user_id,\n'
    '            "temporary_password": "invented01",\n'
    '            "expires_in_hours": 24,\n'
    "        }\n"
    "    reset_password.func = reset_password_inventing\n",
    encoding="utf-8",
)
planted = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_techcorp_tools.py",
        "-q",
        "-k",
        "unknown_user",
        "-p",
        "_plant_inventing",
        "--override-ini",
        "addopts=",
    ],
    cwd=root,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("planted_stdout")
print(planted.stdout)
print("planted_stderr")
print(planted.stderr)
print("planted_exit_code", planted.returncode)
for line in (planted.stdout + "\n" + planted.stderr).splitlines():
    lowered = line.lower()
    if "assert" in lowered or "fail" in lowered or "error" in lowered:
        print("failure_line", line)
plant.unlink(missing_ok=True)
print("plant_removed", not plant.exists())
