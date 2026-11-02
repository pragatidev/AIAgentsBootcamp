"""pgvector reached from retrieve (23.3, 23.4): the deployment picks the store, the scope is a filter in the query.

Fake stores and a hashing embedder stand in here only. The live round trip skips unless Postgres answers.
"""

import importlib
import uuid

import pytest
from langchain_core.documents import Document

import config
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.rag import pgvector_store as PG
from dataflow.rag.faiss_index import build_faiss_index, chunks_with_ids
from dataflow.rag.load import KB_DIR, WIKI_DIR, load_knowledge_base
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.hashing_embeddings import HashingEmbeddings

RT = importlib.import_module("dataflow.tools.retrieve")
RETURN = Document(
    page_content="DataFlow return policy\nReturns are allowed within 30 days of delivery when the item is unused.",
    metadata={"source": "dataflow/wiki/return_policy.md", "folder": "wiki", "heading_path": "DataFlow return policy"},
)


class RecordingStore:
    def __init__(self):
        self.filters = []
        self.added = []

    def similarity_search_with_score(self, question, k=4, filter=None):
        self.filters.append(filter)
        return [(RETURN, 0.21)]

    def add_documents(self, docs, ids=None):
        self.added.append((docs, ids))
        return list(ids or [])


@pytest.fixture
def recording():
    store = RecordingStore()
    RT.set_pg_store(store)
    yield store
    RT.set_pg_store(None)
    RT.reset_index()


def test_store_switch_defaults_to_faiss(tmp_path, recording):
    assert config.RETRIEVE_STORE == "faiss"
    RT.set_index(build_faiss_index(docs=load_knowledge_base(roots=(WIKI_DIR,)), index_dir=tmp_path, embeddings=HashingEmbeddings()))
    rows = RT.retrieve_passages("return window", k=2)
    assert rows and recording.filters == []


def test_pgvector_rows_pass_the_scope_filter(recording):
    rows = RT.retrieve_passages("What is the customer return window?", store="pgvector")
    assert recording.filters == [{"folder": {"$in": ["customer_facing", "wiki"]}}]
    assert rows[0]["source"] == "dataflow/wiki/return_policy.md" and rows[0]["h2"] is None and rows[0]["heading_path"]
    RT.retrieve_passages("refund approval", store="pgvector", scope="support_agent")
    assert recording.filters[-1] == {"folder": {"$in": sorted(RT.SCOPES["support_agent"])}}


def test_the_graph_reads_pgvector_when_built_to(recording):
    fake = FakeChatModel(route="retrieve", reply="Returns are allowed within 30 days of delivery.")
    out = build_rag_graph(model=fake, retrieve_store="pgvector").invoke({"question": "What is the customer return window?"})
    assert recording.filters == [{"folder": {"$in": ["customer_facing", "wiki"]}}]
    assert "dataflow/wiki/return_policy.md" in out["reply"]


def test_index_corpus_uses_stable_ids(recording):
    docs = load_knowledge_base(roots=(KB_DIR / "customer_facing", WIKI_DIR))
    ids = PG.index_corpus(recording, docs)
    assert ids == chunks_with_ids(docs)[1]
    assert len(ids) == len(set(ids))


def test_wrong_width_is_refused_before_any_store_opens():
    class Narrow(HashingEmbeddings):
        def __init__(self):
            super().__init__(dim=8)

    with pytest.raises(ValueError, match="embedder dimension 8 does not match column width 3072"):
        PG.build_pgvector_store("never_opened", embeddings=Narrow(), embedding_length=3072)


@pytest.mark.skipif(not PG.postgres_reachable(), reason="no Postgres reachable (start it with docker compose up -d postgres)")
def test_pgvector_round_trip():
    width = PG.column_width() or 256
    emb = HashingEmbeddings(dim=width)
    name = "test_rag_pgvector_" + uuid.uuid4().hex[:8]
    store = PG.build_pgvector_store(name, embeddings=emb, embedding_length=width, pre_delete_collection=True)
    try:
        docs = load_knowledge_base(roots=(WIKI_DIR,))
        first = PG.index_corpus(store, docs)
        again = PG.index_corpus(store, docs)
        assert first == again
        hits = PG.query(store, "Returns are allowed within 30 days of delivery", k=3, filter={"folder": {"$in": ["wiki"]}})
        assert hits and hits[0]["source"] == "dataflow/wiki/return_policy.md"
        assert PG.column_width() == width
    finally:
        store.delete_collection()
