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
    scope: str = "customer",
) -> dict[str, Any]:
    """Widen retrieval to k=6 inside the caller's scope, once. Still the corpus, never the web.

    The switch keeps its web-search name because widening past the company's own
    pages is a company policy; what ships searches the corpus at k=6. The graph
    reads "widened" and refuses rather than widening twice.
    """
    if not web_search_allowed:
        raise NotImplementedError("web search is a company policy; off by default")
    from dataflow.tools.retrieve import retrieve_passages

    question = state.get("rewritten_question") or state.get("question") or ""
    hits = retrieve_passages(question, k=6, scope=scope)
    return {"passages": hits, "widened": True}


def should_refuse(state: dict[str, Any], *, max_rewrites: int = MAX_REWRITES) -> bool:
    """True when the grader kept nothing (no keep label and no graded passage) and the rewrite budget is spent.

    Retrieval may still have returned passages: empty means nothing survived the grade.
    """
    grades = list(state.get("grades") or [])
    kept = [row for row in grades if str(row.get("label") or "") == "keep"]
    if kept or state.get("graded"):
        return False
    return int(state.get("rewrites") or 0) >= int(max_rewrites)


def build_crag(
    *,
    model: Any = None,
    web_search_allowed: bool = False,
    max_rewrites: int = MAX_REWRITES,
    checkpointer: Any = None,
    policy: Any = None,
):
    """Same nodes as the agentic graph, with after_grade (or the policy passed in) as the edge after grade."""
    from dataflow.graphs.rag_graph import build_rag_graph

    return build_rag_graph(
        model=model,
        checkpointer=checkpointer,
        grade_enabled=True,
        max_rewrites=max_rewrites,
        web_search_allowed=web_search_allowed,
        policy=policy,
    )
