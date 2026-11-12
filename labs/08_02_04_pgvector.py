# %%
"""Lab 23.4: put one DataFlow collection in pgvector.

What we build: you type the small check that keeps the embedder and the vector column the same width,
start the course's Postgres with docker compose, put the support procedures into one pgvector collection
and ask who can approve a refund. Then the agent half: the customer pages go into a second collection, and
the create_agent desk answers a customer from Postgres, not from the FAISS file.

What you learn: 23.3's idea made real. The vectors become rows any copy of the desk can read; the column
is declared once at the embedder's width and checked before any row is written; the database is the last
guard when nothing in Python checked; and the store is a switch the deployment sets, never the model.

What will be true on your screen: the embedder read off the object and your two width_check lines (they
need no Docker), then compose's return code and waiting for postgres ... ready, the column's width read
back from Postgres, the inserted count, the top three hits with their distances and refund_on_top, the
database's one-line refusal of a wrong-width vector, and the desk's reply ending in a Sources line that
names dataflow/wiki/return_policy.md from Postgres. If Docker is not running, the lab prints
BLOCKED ON DOCKER after your width check and exits cleanly. Then python -m pytest tests/test_lab_08_02_04.py -q.
"""

from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config


# %%
# TYPE THIS: check_dimension. The signature and docstring are given; you type the body.
# Its finished copy is dataflow/rag/pgvector_store.py, where build_pgvector_store calls it.
def check_dimension(embeddings, expected: int | None = None) -> int:
    """Embed one string and compare to the column width. Raise before any row is written when they differ."""
    width = len(embeddings.embed_query("dimension probe"))
    if expected is not None and width != expected:
        raise ValueError(f"embedder dimension {width} does not match column width {expected}")
    return width


# BREAK: delete the two lines of the if (the check and its raise), run the lab, and read the
# "width_check column" line: a wrong width now passes. python -m pytest tests/test_lab_08_02_04.py -q goes red.
# git checkout -- labs/08_02_04_pgvector.py puts it back.

emb = config.get_embeddings()
print("embedder", type(emb).__name__, getattr(emb, "model", None) or getattr(emb, "model_name", None))
width = check_dimension(emb)
print("width_check column none ->", width)
try:
    print("width_check column", width + 1, "->", check_dimension(emb, expected=width + 1))
except ValueError as err:
    print("width_check column", width + 1, "-> refused:", err)


# %%
# Start the course's Postgres. Clone and pytest never start Docker; this lab does, once.
from labs._quiet_exit import quiet_exit
from dataflow.rag.pgvector_store import DEFAULT_CONNECTION, build_pgvector_store, column_width, index_corpus, query, wait_for_postgres

print("compose_up")
try:
    compose = subprocess.run(["docker", "compose", "up", "-d", "postgres"], cwd=root, capture_output=True, text=True)
except FileNotFoundError:
    print("BLOCKED ON DOCKER")
    quiet_exit("docker is not installed or not on PATH; install Docker Desktop and run this lab again.")
else:
    print("compose_returncode", compose.returncode)
    if compose.returncode != 0:
        said = (compose.stderr or compose.stdout or "").strip().splitlines()
        print("compose_said", said[-1] if said else "")
        print("BLOCKED ON DOCKER")
        quiet_exit("docker compose could not start Postgres (its last line is above); if Docker is not running, start Docker Desktop and run this lab again.")
    elif not wait_for_postgres(DEFAULT_CONNECTION, seconds=90):
        print("BLOCKED ON POSTGRES")
        quiet_exit("Postgres did not accept connections within 90 seconds: run docker compose logs postgres, then run this lab again.")


# %%
# One collection, the whole procedures file: the refund section has to win, not just be the only row.
from dataflow.rag.load import KB_DIR, WIKI_DIR, load_knowledge_base

column = column_width()
print("column", f"vector({column})" if column else "none yet")
declared = check_dimension(emb, expected=column)
store = build_pgvector_store("dataflow_refunds", embeddings=emb, embedding_length=declared, pre_delete_collection=True)
procedures = KB_DIR / "internal_operations" / "support_operations" / "customer_support_procedures.markdown"
ids = index_corpus(store, load_knowledge_base(roots=(procedures,)))
print("inserted", len(ids))
question = "Who can approve a refund under 30 days?"
print("question", question)
hits = query(store, question, k=3)
for hit in hits:
    print("hit", round(hit["score"], 4), hit["heading_path"])
print("top_source", hits[0]["source"])
print("refund_on_top", hits[0]["heading_path"].endswith("6.1 Authorization Levels"))


# %%
# The database is the last guard: a vector one wider than the column, written past every Python check.
print("break_wrong_width", declared + 1)
try:
    store.add_embeddings(texts=["wrong width vector"], embeddings=[[0.0] * (declared + 1)], metadatas=[{"source": "lab-break"}])
    print("wrong_width_unexpected_success")
except Exception as err:
    print("wrong_width_error", type(err).__name__ + ":", str(err).strip().splitlines()[0])


# %%
# The agent half: the customer pages in their own collection, and the create_agent desk reads it through retrieve.
from dataflow.rag.cite import cite, tool_passages
from dataflow.rag.desk import ask_desk, build_rag_desk, reply_text
from dataflow.tools.retrieve import set_pg_store

customer = build_pgvector_store(config.PGVECTOR_COLLECTION, embeddings=emb, embedding_length=declared, pre_delete_collection=True)
print("customer_collection", config.PGVECTOR_COLLECTION, "inserted", len(index_corpus(customer, load_knowledge_base(roots=(KB_DIR / "customer_facing", WIKI_DIR)))))
set_pg_store(customer)
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
state = ask_desk(build_rag_desk(model=chat, store="pgvector"), "What is the customer return window?", model=chat)
print("tool_calls", [(call["name"], call["args"]) for message in state["messages"] for call in getattr(message, "tool_calls", None) or []])
passages = tool_passages(state["messages"])
print("passages_from_postgres", [row["source"] for row in passages])
print(cite({"reply": reply_text(state), "sources": passages})["reply"])
