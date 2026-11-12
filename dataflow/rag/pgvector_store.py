"""pgvector store for one DataFlow collection.

Vectors live in Postgres next to the checkpointer. A local FAISS file
does not survive two boxes. Tests skip when no database is reachable.

This uses langchain_postgres.PGVector, which keeps every collection in one
shared table, langchain_pg_embedding, whose vector column width is fixed by
the first store ever opened on the database. The package's newer
PGVectorStore runs its engine on an event loop it makes with
asyncio.new_event_loop(), which on Windows is a ProactorEventLoop, and
psycopg's async mode refuses that loop; PGVector's sync psycopg path runs
on every student's machine. The scope filter is a metadata filter that
Postgres applies in the same query as the distance; the distance is cosine.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.documents import Document

from config import get_embeddings

DEFAULT_CONNECTION = os.environ.get(
    "POSTGRES_URL",
    "postgresql://dataflow:dataflow@localhost:5432/dataflow",
)


def check_dimension(embeddings: Any, expected: int | None = None) -> int:
    """Embed one string and compare to the column width."""
    vector = embeddings.embed_query("dimension probe")
    dimension = len(vector)
    if expected is not None and dimension != expected:
        raise ValueError(
            f"embedder dimension {dimension} does not match column width {expected}"
        )
    return dimension


def postgres_reachable(connection: str | None = None) -> bool:
    url = connection or DEFAULT_CONNECTION
    try:
        import psycopg

        conn = psycopg.connect(url, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


def wait_for_postgres(connection: str | None = None, seconds: int = 90) -> bool:
    """Retry until Postgres accepts a connection. A fresh container needs a few seconds."""
    import time

    deadline = time.monotonic() + seconds
    print("waiting for postgres ", end="", flush=True)
    while True:
        if postgres_reachable(connection):
            print(" ready", flush=True)
            return True
        if time.monotonic() >= deadline:
            print(" gave up", flush=True)
            return False
        print(".", end="", flush=True)
        time.sleep(2)


def build_pgvector_store(
    collection: str,
    connection: str | None = None,
    embeddings: Any = None,
    embedding_length: int | None = None,
    pre_delete_collection: bool = False,
):
    """Open a langchain_postgres PGVector collection.

    Declares the vector column from the embedder's measured dimension
    unless embedding_length is passed, then checks they match.
    """
    from langchain_postgres import PGVector

    embeddings = embeddings or get_embeddings()
    dimension = check_dimension(embeddings, expected=embedding_length)
    width = embedding_length if embedding_length is not None else dimension
    if dimension != width:
        raise ValueError(
            f"embedder dimension {dimension} does not match column width {width}"
        )
    url = connection or DEFAULT_CONNECTION
    if url.startswith("postgresql://"):
        # A bare postgresql:// makes SQLAlchemy reach for psycopg2; the course installs psycopg 3.
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    store = PGVector(
        embeddings=embeddings,
        connection=url,
        collection_name=collection,
        embedding_length=width,
        use_jsonb=True,
        pre_delete_collection=pre_delete_collection,
    )
    return store


def insert_docs(store: Any, docs: list[Document]) -> list[str]:
    return store.add_documents(docs)


def column_width(connection: str | None = None) -> int | None:
    """The width Postgres already declared for the shared vector column, or None before any store opened it."""
    import psycopg

    url = connection or DEFAULT_CONNECTION
    with psycopg.connect(url, connect_timeout=5) as conn:
        row = conn.execute(
            "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
            "JOIN pg_class c ON a.attrelid = c.oid "
            "WHERE c.relname = 'langchain_pg_embedding' AND a.attname = 'embedding' AND NOT a.attisdropped"
        ).fetchone()
    if not row or not row[0] or "(" not in row[0]:
        return None
    return int(row[0].split("(", 1)[1].rstrip(")"))


def index_corpus(store: Any, docs: list[Document], chunker: str = "heading") -> list[str]:
    """Chunk the documents and add them with stable ids. The same id again is an update, not a second row."""
    from dataflow.rag.faiss_index import chunks_with_ids

    chunks, ids = chunks_with_ids(docs, chunker)
    if not chunks:
        return []
    return list(store.add_documents(chunks, ids=row_ids(store, ids)))


def query(store: Any, question: str, k: int = 3, filter: dict | None = None) -> list[dict]:
    """Nearest rows, shaped like the FAISS rows. score is the cosine distance: lower is nearer.

    filter is a metadata filter Postgres applies in the same query, for example
    {"folder": {"$in": ["customer_facing", "wiki"]}}.
    """
    pairs = store.similarity_search_with_score(question, k=k, filter=filter)
    rows: list[dict] = []
    for doc, score in pairs:
        meta = dict(doc.metadata or {})
        rows.append(
            {
                "text": doc.page_content,
                "source": meta.get("source", ""),
                "folder": meta.get("folder"),
                "score": float(score),
                "row": meta.get("row"),
                "heading_path": meta.get("heading_path") or "",
                "h2": meta.get("h2"),
                "h3": meta.get("h3"),
            }
        )
    return rows


def row_ids(store: Any, ids: list[str]) -> list[str]:
    """Each stable chunk id with its collection's name in front, so the id is this collection's own.

    The library keeps every collection in one table whose key is the id alone, and
    writing an id that already exists updates that row where it is. Without the name,
    the same file indexed into a second collection would overwrite the first
    collection's rows and add nothing to the second.
    """
    name = getattr(store, "collection_name", None)
    return [f"{name}:{chunk_id}" for chunk_id in ids] if name else list(ids)
