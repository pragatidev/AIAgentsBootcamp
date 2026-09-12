"""8.2 FAISS index, pgvector dimension check, retrieve tool. No Ollama."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from dataflow.graphs.rag_tool_cycle import build_rag_tool_cycle
from dataflow.rag.faiss_index import build_faiss_index, search
from dataflow.rag.load import KB_DIR, WIKI_DIR, load_knowledge_base
from dataflow.rag.pgvector_store import check_dimension, postgres_reachable
from dataflow.tools.retrieve import (
    RETRIEVE_DESCRIPTION,
    reset_index,
    retrieve,
    set_index,
)
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings


def test_faiss_build_and_search(tmp_path):
    embeddings = HashingEmbeddings()
    docs = load_knowledge_base(roots=(WIKI_DIR,))
    index = build_faiss_index(
        docs=docs,
        chunker="heading",
        index_dir=tmp_path,
        embeddings=embeddings,
    )
    hits = search(index, "Can I return an unused item after delivery?", k=3)
    assert hits
    assert "text" in hits[0]
    assert "source" in hits[0]
    assert "folder" in hits[0]
    assert "score" in hits[0]
    sources = " ".join(str(hit.get("source") or "") for hit in hits)
    assert "return_policy.md" in sources.replace("\\", "/")
    assert all(hit.get("folder") == "wiki" for hit in hits)


def test_folder_filter_excludes_hr(tmp_path):
    embeddings = HashingEmbeddings()
    docs = load_knowledge_base(
        roots=(WIKI_DIR, KB_DIR / "internal_operations" / "hr_policies")
    )
    index = build_faiss_index(
        docs=docs,
        chunker="heading",
        index_dir=tmp_path,
        embeddings=embeddings,
    )
    hits = search(
        index,
        "Can I send back an unused lamp after twelve days?",
        k=5,
        folder="wiki",
    )
    assert hits
    for hit in hits:
        source = str(hit.get("source") or "").replace("\\", "/")
        assert "employee_handbook" not in source
        assert hit.get("folder") == "wiki"


def test_retrieve_is_a_tool():
    assert retrieve.name == "retrieve"
    assert "question" in retrieve.args
    assert RETRIEVE_DESCRIPTION
    assert retrieve.description
    assert len(retrieve.description) > 10


def test_cycle_calls_retrieve_on_policy_question(tmp_path):
    embeddings = HashingEmbeddings()
    docs = load_knowledge_base(roots=(WIKI_DIR,))
    index = build_faiss_index(
        docs=docs,
        chunker="heading",
        index_dir=tmp_path,
        embeddings=embeddings,
    )
    set_index(index)
    try:
        model = FakeToolModel(
            script=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "retrieve",
                            "args": {
                                "question": "What is the return window?",
                                "k": 3,
                            },
                            "id": "call_retrieve",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="Returns are allowed within 30 days of delivery."),
            ]
        )
        graph = build_rag_tool_cycle(model=model)
        out = graph.invoke(
            {
                "messages": [
                    HumanMessage(content="What is the return window?")
                ]
            }
        )
        messages = out["messages"]
        assert any(isinstance(msg, ToolMessage) for msg in messages)
        tool_msg = next(msg for msg in messages if isinstance(msg, ToolMessage))
        assert tool_msg.name == "retrieve"
        assert "source" in str(tool_msg.content)
        assert isinstance(messages[-1], AIMessage)
        assert not (getattr(messages[-1], "tool_calls", None) or [])
    finally:
        reset_index()


def test_pgvector_dimension_check():
    class _Emb:
        def embed_query(self, text: str) -> list[float]:
            return [0.0] * 8

    assert check_dimension(_Emb(), expected=8) == 8
    try:
        check_dimension(_Emb(), expected=3072)
        raise AssertionError("dimension mismatch should raise")
    except ValueError as err:
        message = str(err)
        assert "8" in message
        assert "3072" in message
    if not postgres_reachable():
        return
