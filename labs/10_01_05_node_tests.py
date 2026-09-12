# %% [markdown]
# Unit-test the DataFlow classify and refuse nodes.
#
# When this works, the two node tests are green, the refuse test as
# first written never calls retrieve, empty hits through the real
# retrieve path go red because the graph skipped refuse, and the
# wiring fix makes the same query green for the right reason.

# %%
from pathlib import Path
import inspect
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.rag.faiss_index import build_faiss_index
from dataflow.tools.retrieve import reset_index, set_index
from langchain_core.documents import Document
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings
from tests.test_nodes_dataflow import (
    test_classify_three_tickets,
    test_refuse_on_empty_retrieve,
)

print("model", config.CHAT_MODEL)
print("running_two_node_tests")
test_classify_three_tickets()
print("test_classify_three_tickets", "PASS")
test_refuse_on_empty_retrieve()
print("test_refuse_on_empty_retrieve", "PASS")

# %%
print("cell", "planted_trap")
# Planted trap. The refuse test as first written never calls retrieve.
# It hands the node an already empty state, so it proves the template
# and nothing about the edge that leads there.
source = inspect.getsource(test_refuse_on_empty_retrieve)
print("refuse_test_source")
print(source)
# The def line carries the word retrieve in the test's own name, so the
# check reads the body only.
body = source.split("\n", 1)[1]
calls_retrieve = any(
    token in body
    for token in ("retrieve(", "retrieve_node", "get_index", "retrieve_passages")
)
print("refuse_test_calls_retrieve", calls_retrieve)
print("refuse_test_calls_refuse_node", "refuse(" in source)

# %%
print("cell", "empty_hits_skip_refuse")
docs = [
    Document(
        page_content="Return equipment within 30 days of termination.",
        metadata={
            "source": (
                "dataflow/knowledge_base/internal_operations/"
                "hr_policies/employee_handbook.txt"
            ),
            "folder": "internal_operations",
        },
    )
]
index = build_faiss_index(
    docs=docs,
    chunker="heading",
    index_dir=None,
    embeddings=HashingEmbeddings(),
)
set_index(index)
query = "xylophone nebula docking tariff"
print("query", query)
print("planted_corpus_folder", "internal_operations")
skipped = build_rag_graph(
    model=FakeChatModel(
        route="retrieve",
        reply="DataFlow covers xylophone insurance worldwide.",
    ),
    grade_enabled=False,
    max_rewrites=0,
    scope="customer",
)
skipped_out = skipped.invoke({"question": query})
skipped_reply = str(skipped_out.get("reply") or "")
skipped_refused = "I do not have that in the knowledge base" in skipped_reply
print("wiring", "retrieve -> generate (grade_enabled=False)")
print("skipped_reply")
print(skipped_reply)
print("skipped_refused", skipped_refused)
print("test_red_wrong_reason", not skipped_refused)
print(
    "why_red",
    "graph wiring skipped refuse; generate wrote a fluent answer",
)

# %%
print("cell", "fix_wiring")
query = "xylophone nebula docking tariff"
fixed = build_rag_graph(
    model=FakeChatModel(route="retrieve", reply="unused"),
    grade_enabled=True,
    max_rewrites=0,
    scope="customer",
)
fixed_out = fixed.invoke({"question": query})
fixed_reply = str(fixed_out.get("reply") or "")
fixed_refused = "I do not have that in the knowledge base" in fixed_reply
print("wiring", "retrieve -> grade -> refuse (max_rewrites=0)")
print("fixed_reply")
print(fixed_reply)
print("fixed_sources", fixed_out.get("sources"))
print("fixed_refused", fixed_refused)
print("test_green_right_reason", fixed_refused)
print(
    "why_green",
    "empty customer-scope hits reached refuse, not generate",
)
reset_index()
print("index_reset", True)

# %%
print("cell", "pytest")
result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_nodes_dataflow.py",
        "-q",
        "--override-ini",
        "addopts=",
    ],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print(result.stdout)
print(result.stderr)
print("pytest_exit", result.returncode)
