"""Retrieve as a LangGraph tool. FAISS by default, customer scope.

The docstring is the routing rule the model reads. An empty
description means the desk never calls this tool.
"""

from __future__ import annotations

from typing import Any

from langchain.tools import tool
from langchain_core.tools import StructuredTool

from dataflow.rag.faiss_index import (
    INDEX_DIR,
    build_faiss_index,
    load_faiss_index,
    search,
)

RETRIEVE_DESCRIPTION = (
    "Search the DataFlow customer policies and guides (wiki and customer facing pages) "
    "for a customer question. Returns passages with their source file."
)

CUSTOMER_FOLDERS = frozenset({"wiki", "customer_facing"})

_INDEX: Any = None


def set_index(index: Any) -> None:
    """Tests inject a hashing index so pytest stays off Ollama."""
    global _INDEX
    _INDEX = index


def reset_index() -> None:
    global _INDEX
    _INDEX = None


def get_index(embeddings: Any = None):
    """Load the FAISS index, building it on first use."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    faiss_file = INDEX_DIR / "index.faiss"
    if faiss_file.is_file():
        _INDEX = load_faiss_index(INDEX_DIR, embeddings=embeddings)
    else:
        _INDEX = build_faiss_index(embeddings=embeddings, index_dir=INDEX_DIR)
    return _INDEX


def retrieve_passages(
    question: str,
    k: int = 3,
    folder: str | None = None,
) -> list[dict]:
    """Search the index. folder=None keeps the customer-facing scope."""
    index = get_index()
    if folder:
        return search(index, question, k=k, folder=folder)
    fetched = search(index, question, k=max(k * 10, 32), folder=None)
    scoped = [row for row in fetched if row.get("folder") in CUSTOMER_FOLDERS]
    return scoped[:k]


@tool
def retrieve(question: str, k: int = 3, folder: str | None = None) -> list[dict]:
    """Search the DataFlow customer policies and guides (wiki and customer facing pages) for a customer question. Returns passages with their source file."""
    return retrieve_passages(question, k=k, folder=folder)


def build_retrieve_tool(description: str | None = None) -> StructuredTool:
    """Rebuild the tool so a lab can blank RETRIEVE_DESCRIPTION."""
    desc = RETRIEVE_DESCRIPTION if description is None else description
    return StructuredTool.from_function(
        func=retrieve_passages,
        name="retrieve",
        description=desc,
    )


retrieve.description = RETRIEVE_DESCRIPTION
