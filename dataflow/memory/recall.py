"""Similarity recall inside a customer namespace."""

from __future__ import annotations

from typing import Any

from langgraph.store.memory import InMemoryStore

import config


def build_recall_store(embedder=None, dims: int = 768) -> InMemoryStore:
    embed = embedder or config.get_embeddings()
    return InMemoryStore(index={"embed": embed, "dims": dims})


def file_note(store: InMemoryStore, customer_id: str, key: str, text: str) -> None:
    store.put(("customers", str(customer_id)), key, {"text": text})


def recall(
    store: InMemoryStore,
    customer_id: str,
    query: str,
    floor: float = 0.0,
    limit: int = 5,
) -> list[dict[str, Any]]:
    hits = store.search(("customers", str(customer_id)), query=query, limit=limit)
    out: list[dict[str, Any]] = []
    for item in hits:
        score = 0.0 if item.score is None else float(item.score)
        if score < floor:
            continue
        out.append(
            {
                "key": item.key,
                "value": item.value,
                "score": score,
                "namespace": item.namespace,
            }
        )
    return out
