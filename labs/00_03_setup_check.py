# %% [markdown]
# Set up Python, VS Code, Git and the repo.
#
# When this works, pytest exits 0 on this machine with no cloud key.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

print("python", sys.version.split()[0], flush=True)
print("venv", sys.prefix, flush=True)

# %%
branch = subprocess.run(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    cwd=root,
    check=False,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("git_branch", (branch.stdout or "").strip() or "(not a git checkout)", flush=True)

# %%
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", result.returncode)
if result.returncode == 0:
    print("GREEN: your setup works. Go on to the next lecture.")
else:
    print(
        "NOT GREEN: read the FAILED or ERROR lines above, look them up in "
        "TROUBLESHOOTING.md, fix, and run this check again."
    )
if "__file__" in globals():
    sys.exit(result.returncode)
