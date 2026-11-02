"""Hybrid search: keyword (BM25) beside dense, fused by reciprocal rank (24.7).

A dense embedding puts meaning in a vector, so an exact token such as an error
code can sit far from the question; BM25 scores the exact words. Reciprocal rank
fusion adds 1 / (k + rank) for every list a passage appears in, so a passage
both lists rank high wins, and neither score scale has to match the other.
k = 60 is the constant of the paper that named the method (Cormack, Clarke and
Buettcher, SIGIR 2009). The library's version is
langchain_classic.retrievers.EnsembleRetriever. Advanced RAG owns the depth.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.documents import Document

RRF_K = 60

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    """Lower-case words, keeping hyphenated codes such as perm-5005 whole."""
    return _TOKEN.findall((text or "").lower())


def build_bm25(chunks: list[Document]):
    """A BM25 keyword index over the chunks (needs the rank-bm25 package)."""
    from langchain_community.retrievers import BM25Retriever

    return BM25Retriever.from_documents(chunks, preprocess_func=tokenize)


def bm25_rows(bm25: Any, question: str, k: int, folders: frozenset[str] | None = None) -> list[dict]:
    """The top k chunks by BM25, as the same row dicts FAISS search returns. score is BM25's: higher is nearer."""
    from dataflow.rag.faiss_index import _row_payload

    scores = bm25.vectorizer.get_scores(tokenize(question))
    order = sorted(range(len(bm25.docs)), key=lambda i: -scores[i])
    rows: list[dict] = []
    for i in order:
        row = _row_payload(bm25.docs[i], float(scores[i]))
        if folders is not None and row.get("folder") not in folders:
            continue
        rows.append(row)
        if len(rows) >= k:
            break
    return rows


def row_key(row: dict) -> tuple:
    """One chunk, whichever list it came from: its file, csv row, and offset (or its text when there is none)."""
    place = row.get("start_index")
    return (row.get("source"), row.get("row"), place if place is not None else row.get("text"))


def reciprocal_rank_fusion(ranked_lists: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """Fuse ranked lists: each chunk scores the sum of 1 / (k + rank) over the lists it is in, rank counted from 1.

    A chunk in two lists is one row. Returns the rows best first, each with its "rrf" score.
    """
    fused: dict[tuple, dict] = {}
    for ranked in ranked_lists:
        for rank, row in enumerate(ranked, start=1):
            key = row_key(row)
            if key not in fused:
                fused[key] = {**row, "rrf": 0.0}
            fused[key]["rrf"] += 1.0 / (k + rank)
    return sorted(fused.values(), key=lambda row: -row["rrf"])


_BM25_FOR: dict[int, Any] = {}


def bm25_for_index(index: Any):
    """The BM25 index over a FAISS index's own chunks, built once per index object."""
    key = id(index)
    if key not in _BM25_FOR:
        _BM25_FOR[key] = build_bm25(list(index.docstore._dict.values()))
    return _BM25_FOR[key]


def hybrid_rows(index: Any, question: str, k: int, folders: frozenset[str], fetch: int = 10) -> list[dict]:
    """Dense and BM25 top `fetch` inside the folders, fused, cut to k."""
    from dataflow.rag.faiss_index import search

    dense = [row for row in search(index, question, k=max(fetch * 4, 32), folder=None) if row.get("folder") in folders][:fetch]
    keyword = bm25_rows(bm25_for_index(index), question, fetch, folders)
    return reciprocal_rank_fusion([dense, keyword])[:k]
