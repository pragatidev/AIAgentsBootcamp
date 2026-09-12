"""10.1 DataFlow node tests. Classify and refuse. Pytest stays green with no key."""

from __future__ import annotations

import pytest
from langchain_core.documents import Document

from dataflow.graphs.rag_graph import REFUSE_TEMPLATE, build_rag_graph, refuse
from dataflow.graphs.v4_hitl import classify
from dataflow.rag.faiss_index import build_faiss_index
from dataflow.tools.retrieve import reset_index, set_index
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings


def _ollama_up() -> bool:
    import json
    import urllib.error
    import urllib.request

    import config

    url = config.OLLAMA_BASE_URL.rstrip("/") + "/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        data = json.loads(body) if body.startswith("{") else {}
        names = [str(m.get("name") or "") for m in data.get("models") or []]
        return any(config.CHAT_MODEL in name for name in names)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def test_classify_three_tickets():
    tickets = [
        ("Where is order DF-1001?", "lookup"),
        ("What is the customer return window?", "policy"),
        ("Please refund order DF-1001. The desk lamp is unused.", "refund"),
    ]
    for ticket, expected in tickets:
        model = FakeChatModel(route=expected)
        out = classify({"ticket": ticket}, model=model)
        assert out["route"] == expected


def test_refuse_on_empty_retrieve():
    state = {
        "question": "Do you sell coffee beans in the DataFlow shop?",
        "graded": [],
        "passages": [],
    }
    out = refuse(state)
    expected = REFUSE_TEMPLATE.format(q=state["question"])
    assert out["reply"] == expected
    assert out["answer"] == expected
    assert out["sources"] == []


def test_classify_one_ticket_live():
    """Skip without Ollama. Real model from config classifies one ticket."""
    if not _ollama_up():
        pytest.skip("no local model")
    from config import get_chat_model

    out = classify(
        {"ticket": "Where is order DF-1001?"},
        model=get_chat_model(),
    )
    assert out["route"] == "lookup"


def test_empty_hits_through_retrieve_reach_refuse(tmp_path):
    """Hashing index over a planted internal corpus cannot match a
    customer-scope query, so retrieve returns no kept passages and the
    graph must take the refuse edge. grade_enabled=False skips refuse.
    """
    docs = [
        Document(
            page_content="Return equipment within 30 days of termination.",
            metadata={
                "source": "dataflow/knowledge_base/internal_operations/hr_policies/employee_handbook.txt",
                "folder": "internal_operations",
            },
        )
    ]
    index = build_faiss_index(
        docs=docs,
        chunker="heading",
        index_dir=tmp_path,
        embeddings=HashingEmbeddings(),
    )
    set_index(index)
    query = "xylophone nebula docking tariff"
    try:
        broken = build_rag_graph(
            model=FakeChatModel(
                route="retrieve",
                reply="DataFlow covers xylophone insurance worldwide.",
            ),
            grade_enabled=False,
            max_rewrites=0,
            scope="customer",
        )
        skipped = broken.invoke({"question": query})
        assert "I do not have that in the knowledge base" not in str(
            skipped.get("reply") or ""
        )
        fixed = build_rag_graph(
            model=FakeChatModel(route="retrieve", reply="unused"),
            grade_enabled=True,
            max_rewrites=0,
            scope="customer",
        )
        reached = fixed.invoke({"question": query})
        assert "I do not have that in the knowledge base" in str(
            reached.get("reply") or ""
        )
        assert reached.get("sources") == []
    finally:
        reset_index()
