# %%
"""S4.5 Walk the DataFlow package. Empty folders they will fill."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# %%
root = Path(__file__).resolve().parents[1]
must = [
    root / "config.py",
    root / "dataflow" / "tools",
    root / "dataflow" / "graphs",
    root / "dataflow" / "evals",
    root / "docs" / "CURRENCY.md",
]

# %%
for path in must:
    print(path.relative_to(root).as_posix(), "ok" if path.exists() else "MISSING")
