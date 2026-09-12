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

# Two indexes, two folders. The customer index is the one lab 23.2 builds
# (customer facing, business data, wiki) and the retrieve tool searches.
# The "all" index holds every knowledge base folder, internal ones
# included, for the graphs built with scope="all". They never share a
# folder, so the order you run the labs in cannot change what a scope sees.
INDEX_ALL_DIR = INDEX_DIR.parent / "faiss_index_all"

_INDEX: Any = None
_INDEX_ALL: Any = None


def set_index(index: Any) -> None:
    """Tests inject a hashing index so pytest stays off Ollama. Both scopes."""
    global _INDEX, _INDEX_ALL
    _INDEX = index
    _INDEX_ALL = index


def reset_index() -> None:
    global _INDEX, _INDEX_ALL
    _INDEX = None
    _INDEX_ALL = None


def get_index(embeddings: Any = None, scope: str = "customer"):
    """Load the FAISS index for a scope, building it on first use.

    scope="customer" is the index under INDEX_DIR. scope="all" is the
    full knowledge base under INDEX_ALL_DIR, built from every folder.
    """
    global _INDEX, _INDEX_ALL
    if scope == "all":
        if _INDEX_ALL is not None:
            return _INDEX_ALL
        if (INDEX_ALL_DIR / "index.faiss").is_file():
            _INDEX_ALL = load_faiss_index(INDEX_ALL_DIR, embeddings=embeddings)
        else:
            _INDEX_ALL = build_faiss_index(
                embeddings=embeddings, index_dir=INDEX_ALL_DIR
            )
        return _INDEX_ALL
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
