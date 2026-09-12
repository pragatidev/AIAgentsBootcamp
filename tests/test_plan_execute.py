"""12.1.4 Plan and execute. Pytest stays green with no live model."""

from langchain_core.documents import Document

from dataflow.graphs.plan_execute import execute
from dataflow.rag.faiss_index import build_faiss_index
from dataflow.tools.retrieve import reset_index, set_index
from tests.fixtures.hashing_embeddings import HashingEmbeddings

TICKET = "I was charged twice for order DF-1003, please check and fix"
RETRIEVE_ONLY = {
    "steps": [{"tool": "retrieve", "why": "read the refund policy"}],
}


def _index(tmp_path):
    docs = [
        Document(
            page_content=(
                "Duplicate charges are reversed after the desk looks up the order "
                "and reads this refund policy."
            ),
            metadata={
                "source": "dataflow/wiki/return_policy.md",
                "folder": "wiki",
            },
        )
    ]
    return build_faiss_index(
        docs=docs,
        chunker="heading",
        index_dir=tmp_path,
        embeddings=HashingEmbeddings(),
    )


def test_execute_runs_retrieve_and_blocks_lookup(tmp_path):
    set_index(_index(tmp_path))
    try:
        out = execute({"ticket": TICKET, "plan": RETRIEVE_ONLY})
    finally:
        reset_index()
    trace = list(out.get("trace") or [])
    ran = [row for row in trace if not row.get("blocked")]
    blocked = [row for row in trace if row.get("blocked")]
    assert any(row.get("tool") == "retrieve" for row in ran)
    lookup = [
        row
        for row in blocked
        if row.get("tool") == "lookup_order_by_id"
    ]
    assert lookup
    assert lookup[0].get("blocked") is True
    assert lookup[0].get("reason") == "not in plan"
    assert "result" not in lookup[0]


def test_planted_execute_runs_unplanned_lookup(tmp_path):
    set_index(_index(tmp_path))
    try:
        out = execute(
            {"ticket": TICKET, "plan": RETRIEVE_ONLY},
            plant_unplanned_lookup=True,
        )
    finally:
        reset_index()
    trace = list(out.get("trace") or [])
    lookup = [
        row
        for row in trace
        if row.get("tool") == "lookup_order_by_id"
    ]
    assert lookup
    assert not lookup[0].get("blocked")
    result = lookup[0].get("result") or {}
    assert result.get("found") is True
    assert result.get("order_id") == "DF-1003"
