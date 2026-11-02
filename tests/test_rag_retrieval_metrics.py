"""Retrieval alone (25.8) and the refusal axis (25.5). Hand-made passages and a scripted judge, here only. No Ollama."""

import pytest

import config
from eval.runners import rag_metrics as M

POLICY_ROW = {"id": "policy-return", "kind": "policy", "question": "What is the customer return window?", "expected_source": "dataflow/wiki/return_policy.md"}
REFUSE_ROW = {"id": "refuse-coffee", "kind": "refuse", "question": "Do you sell coffee beans in the DataFlow shop?"}
REFUSAL = "I do not have that in the knowledge base. I understood the question as: x. You can rephrase it or ask to speak to a person."


def _p(source):
    return {"source": source, "text": "t"}


def test_recall_and_mrr_known_answer():
    passages = [_p("dataflow/wiki/shipping.md"), _p("dataflow/wiki/return_policy.md"), _p("dataflow/wiki/security.md")]
    assert M.retrieval_metrics(POLICY_ROW, passages) == {
        "id": "policy-return", "rank": 1, "recall_at_1": 0, "recall_at_3": 1, "recall_at_5": 1, "mrr": 0.5,
    }
    missing = M.retrieval_metrics(POLICY_ROW, [_p("a.md")] * 5)
    assert missing["rank"] is None and missing["mrr"] == 0.0 and missing["recall_at_5"] == 0


def test_rows_without_source_are_excluded():
    assert M.retrieval_metrics(REFUSE_ROW, [_p("dataflow/wiki/return_policy.md")]) is None
    table = M.retrieval_table([POLICY_ROW, REFUSE_ROW], lambda q: [_p("dataflow/wiki/return_policy.md")])
    assert table["scored"] == 1 and table["left_out"] == 1 and table["means"]["mrr"] == 1.0


def test_the_question_file_has_seven_rows_with_a_file():
    rows = M.load_questions()
    assert len(rows) == 12 and sum(1 for r in rows if r.get("expected_source")) == 7


def test_context_recall_definition_unchanged():
    judge = lambda answer, passages, model=None: 1  # noqa: E731
    refuse = M.score_row(REFUSE_ROW, {"answer": REFUSAL, "passages": [], "sources": []}, judge=judge)
    assert refuse["context_recall"] == 1
    miss = M.score_row(POLICY_ROW, {"answer": "30 days", "passages": [_p("other.md")], "sources": []}, judge=judge)
    assert miss["context_recall"] == 0


def test_score_row_keys_unchanged():
    out = M.score_row(POLICY_ROW, {"answer": "30 days", "passages": [_p("dataflow/wiki/return_policy.md")], "sources": []}, judge=lambda a, p, model=None: 1)
    assert sorted(out) == sorted(["id", "kind", "faithfulness", "context_recall", "refused_correctly", "fluent_miss", "answer", "route"])


def test_retrieval_only_needs_no_chat_model(monkeypatch, tmp_path):
    from dataflow.rag.faiss_index import build_faiss_index
    from dataflow.rag.load import WIKI_DIR, load_knowledge_base
    from tests.fixtures.hashing_embeddings import HashingEmbeddings

    def no_model(**kwargs):
        raise AssertionError("retrieval-only metrics called a chat model")

    monkeypatch.setattr(config, "get_chat_model", no_model)
    index = build_faiss_index(docs=load_knowledge_base(roots=(WIKI_DIR,)), index_dir=tmp_path, embeddings=HashingEmbeddings())
    passages = M.run_retrieval_only("customer return window 30 days delivery", k=3, index=index)
    assert M.retrieval_metrics(POLICY_ROW, passages)["recall_at_3"] == 1


class CountingJudge:
    def __init__(self):
        self.calls = 0

    def __call__(self, answer, passages, model=None):
        self.calls += 1
        return 0 if "lifetime warranty" in answer else 1


@pytest.mark.parametrize(
    "kind, answer, expected, calls",
    [
        ("refuse", REFUSAL, {"refused": True, "refused_correctly": 1, "faithfulness": 1, "fluent_miss": False, "over_refusal": False}, 0),
        ("refuse", "Yes, every desk lamp has a lifetime warranty.", {"refused": False, "refused_correctly": 0, "faithfulness": 0, "fluent_miss": True, "over_refusal": False}, 1),
        ("refuse", "I don't have information about a lifetime warranty.", {"refused": False, "refused_correctly": 0, "faithfulness": 0, "fluent_miss": True, "over_refusal": False}, 1),
        ("policy", REFUSAL, {"refused": True, "refused_correctly": 0, "faithfulness": 1, "fluent_miss": False, "over_refusal": True}, 0),
        ("policy", "Returns are allowed within 30 days.", {"refused": False, "refused_correctly": 0, "faithfulness": 1, "fluent_miss": False, "over_refusal": False}, 1),
    ],
)
def test_refusal_scores(kind, answer, expected, calls):
    judge = CountingJudge()
    assert M.refusal_scores(kind, answer, [], judge=judge) == expected
    assert judge.calls == calls
