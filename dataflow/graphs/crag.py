"""Corrective RAG policy: rewrite once, widen only inside the corpus, refuse.

Web search is a company policy and ships off.
"""

from __future__ import annotations

from typing import Any

MAX_REWRITES = 1


def after_grade(
    state: dict[str, Any],
    *,
    max_rewrites: int = MAX_REWRITES,
    web_search_allowed: bool = False,
) -> str:
    """Pick generate, rewrite, widen, or refuse after the grade node."""
    grades = list(state.get("grades") or [])
    kept = [row for row in grades if str(row.get("label") or "") == "keep"]
    if not kept:
        kept = list(state.get("graded") or [])
    if kept:
        return "generate"
    spent = int(state.get("rewrites") or 0)
    if spent < int(max_rewrites):
        return "rewrite"
    if web_search_allowed:
        return "widen"
    return "refuse"


def widen(
    state: dict[str, Any],
    *,
    web_search_allowed: bool = False,
) -> dict[str, Any]:
    """Widen retrieval to k=6 over every folder. Still inside the corpus."""
    if not web_search_allowed:
        raise NotImplementedError("web search is a company policy; off by default")
    from dataflow.rag.faiss_index import search
    from dataflow.tools.retrieve import get_index

    question = state.get("rewritten_question") or state.get("question") or ""
    hits = search(get_index(), question, k=6, folder=None)
    return {"passages": hits}


def build_crag(
    *,
    model: Any = None,
    web_search_allowed: bool = False,
    max_rewrites: int = MAX_REWRITES,
    checkpointer: Any = None,
):
    """Same nodes as the agentic graph, with after_grade as the policy edge."""
    from dataflow.graphs.rag_graph import build_rag_graph

    return build_rag_graph(
        model=model,
        checkpointer=checkpointer,
        grade_enabled=True,
        max_rewrites=max_rewrites,
        web_search_allowed=web_search_allowed,
    )
