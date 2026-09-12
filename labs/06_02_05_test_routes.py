# %% [markdown]
# Test routes with pytest fixtures.
#
# When this works, tests/test_dataflow_routes.py is green with no
# live key and this lab prints the pytest exit code.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_dataflow_routes.py", "-q"],
    cwd=root,
    check=False,
)
print("pytest_exit", result.returncode)
