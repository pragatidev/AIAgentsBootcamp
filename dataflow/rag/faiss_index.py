"""FAISS index for the DataFlow knowledge base.

One embedder from config builds the index and queries it. A laptop
lab can stay on this file; pgvector is the production swap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from config import ROOT, get_embeddings
from dataflow.rag.chunk import chunk_by_heading, chunk_recursive, heading_path
from dataflow.rag.load import load_knowledge_base

INDEX_DIR = ROOT / "dataflow" / "data" / "faiss_index"


def measured_dimension(embeddings: Any = None) -> int:
    """Embed one short string once. This is the column width."""
    embeddings = embeddings or get_embeddings()
    vector = embeddings.embed_query("dimension probe")
    return len(vector)


def _chunks_for(docs: list[Document], chunker: str) -> list[Document]:
    if chunker == "heading":
        return chunk_by_heading(docs)
    return chunk_recursive(docs, chunk_size=1000, chunk_overlap=0)


def build_faiss_index(
    docs: list[Document] | None = None,
    chunker: str = "heading",
    index_dir: Path | str | None = INDEX_DIR,
    embeddings: Any = None,
) -> FAISS:
    """Build a FAISS index. Writes to index_dir when that path is set."""
    embeddings = embeddings or get_embeddings()
    if docs is None:
        docs = load_knowledge_base()
    chunks = _chunks_for(docs, chunker)
    if not chunks:
        raise ValueError("no chunks to index")
    index = FAISS.from_documents(chunks, embeddings)
    if index_dir is not None:
        path = Path(index_dir)
        path.mkdir(parents=True, exist_ok=True)
        index.save_local(str(path))
    return index


def load_faiss_index(
    index_dir: Path | str = INDEX_DIR,
    embeddings: Any = None,
) -> FAISS:
    embeddings = embeddings or get_embeddings()
    return FAISS.load_local(
        str(index_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def _row_payload(doc: Document, score: float) -> dict:
    meta = dict(doc.metadata or {})
    path = heading_path(meta) or meta.get("heading_path") or ""
    return {
        "text": doc.page_content,
        "source": meta.get("source", ""),
        "folder": meta.get("folder"),
        "score": float(score),
        "row": meta.get("row"),
        "heading_path": path,
        "h2": meta.get("h2"),
        "h3": meta.get("h3"),
    }


def search(
    index: FAISS,
    question: str,
    k: int = 3,
    folder: str | None = None,
) -> list[dict]:
    """Nearest passages. Folder filter runs after fetch, then cut to k."""
    fetch = k if not folder else max(k * 10, 32)
    pairs = index.similarity_search_with_score(question, k=fetch)
    rows: list[dict] = []
    for doc, score in pairs:
        item = _row_payload(doc, score)
        if folder and item.get("folder") != folder:
            continue
        rows.append(item)
        if len(rows) >= k:
            break
    return rows


if __name__ == "__main__":
    built = build_faiss_index()
    width = measured_dimension()
    print("index_dir", INDEX_DIR.as_posix())
    print("dimension", width)
    print("built", type(built).__name__)
