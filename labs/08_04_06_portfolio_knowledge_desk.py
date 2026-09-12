# %% [markdown]
# Portfolio: DataFlow knowledge desk with FAISS retrieve.
#
# When this works, three tickets print: a policy with a citation, an
# unknown that refuses, and an order id that does not retrieve. Then
# pytest on tests/test_rag_*.py is green.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from config import CHAT_MODEL
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.tools.retrieve import get_index

print("model", CHAT_MODEL)
print("building_index")
get_index(scope="all")
print("index_ready")
graph = build_rag_graph(scope="all")

tickets = [
    ("policy", "Who can approve a refund under 30 days?"),
    ("unknown", "Do you sell coffee beans in the DataFlow shop?"),
    ("order", "Where is order DF-1002?"),
]
for label, text in tickets:
    print("ticket", label)
    print("text", text)
    state = graph.invoke({"question": text})
    print("route", state.get("route"))
    print("reply")
    print(state.get("reply"))
    retrieved = bool(state.get("passages"))
    print("retrieved", retrieved)
    print("---")

# %%
rag_tests = sorted(str(path) for path in (root / "tests").glob("test_rag_*.py"))
result = subprocess.run(
    [sys.executable, "-m", "pytest", *rag_tests, "-q", "--override-ini", "addopts="],
    cwd=root,
    check=False,
)
print("pytest_files", rag_tests)
print("pytest_exit", result.returncode)
