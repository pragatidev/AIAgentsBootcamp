# %%
"""S1.3 Clone contract. No API key."""

from pathlib import Path
import subprocess
import sys

# %%
root = Path(__file__).resolve().parents[1]
print("python", sys.version.split()[0])
print("root", root)

# %%
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", result.returncode)
