"""pgvector store for one DataFlow collection.

Vectors live in Postgres next to the checkpointer. A local FAISS file
does not survive two boxes. Tests skip when no database is reachable.
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
    store = PGVector(
        embeddings=embeddings,
        connection=connection or DEFAULT_CONNECTION,
        collection_name=collection,
        embedding_length=width,
        use_jsonb=True,
        pre_delete_collection=pre_delete_collection,
    )
    return store


def insert_docs(store: Any, docs: list[Document]) -> list[str]:
    return store.add_documents(docs)


def query(store: Any, question: str, k: int = 3) -> list[dict]:
    pairs = store.similarity_search_with_score(question, k=k)
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
                "heading_path": meta.get("heading_path"),
            }
        )
    return rows
