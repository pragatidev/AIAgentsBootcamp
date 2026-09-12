# %% [markdown]
# Put one DataFlow collection in pgvector.
#
# When this works, docker compose starts Postgres, the refund
# procedure is inserted, and a query prints the row and its source.
# Insert a vector of the wrong width and print the database error.
# If Docker is down, this lab prints BLOCKED ON DOCKER and exits 0.

# %%
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_community.document_loaders import TextLoader

from dataflow.rag.chunk import chunk_by_heading
from dataflow.rag.load import KB_DIR
from dataflow.rag.pgvector_store import (
    DEFAULT_CONNECTION,
    build_pgvector_store,
    insert_docs,
    postgres_reachable,
    query,
)

print("compose_up")
compose = subprocess.run(
    ["docker", "compose", "up", "-d", "postgres"],
    cwd=root,
    capture_output=True,
    text=True,
)
print("compose_returncode", compose.returncode)
if compose.stdout:
    print(compose.stdout)
if compose.stderr:
    print(compose.stderr)
if compose.returncode != 0:
    print("BLOCKED ON DOCKER")
    sys.exit(0)

if not postgres_reachable(DEFAULT_CONNECTION):
    print("BLOCKED ON DOCKER")
    print("postgres is not reachable at", DEFAULT_CONNECTION)
    sys.exit(0)

# %%
path = (
    KB_DIR
    / "internal_operations"
    / "support_operations"
    / "customer_support_procedures.markdown"
)
loaded = TextLoader(str(path), encoding="utf-8").load()
loaded[0].metadata["source"] = (
    "dataflow/knowledge_base/internal_operations/"
    "support_operations/customer_support_procedures.markdown"
)
loaded[0].metadata["folder"] = "internal_operations"
chunks = chunk_by_heading(loaded)
refund = [
    chunk
    for chunk in chunks
    if chunk.metadata.get("h3") == "6.1 Authorization Levels"
]
print("refund_chunks", len(refund))
store = build_pgvector_store(
    "dataflow_refunds",
    connection=DEFAULT_CONNECTION,
    pre_delete_collection=True,
)
ids = insert_docs(store, refund)
print("inserted", len(ids))
question = "Who can approve a refund under 30 days?"
print("question", question)
hits = query(store, question, k=3)
print("hit_count", len(hits))
if hits:
    print("source", hits[0].get("source"))
    print("heading_path", hits[0].get("heading_path"))
    print("row")
    print(hits[0].get("text", "")[:500])

# %%
print("break_wrong_width")
try:
    fake = [0.0] * 3072
    store.add_embeddings(
        texts=["wrong width vector"],
        embeddings=[fake],
        metadatas=[{"source": "lab-break"}],
    )
    print("wrong_width_unexpected_success")
except Exception as err:
    print("wrong_width_error", type(err).__name__ + ":", err)
