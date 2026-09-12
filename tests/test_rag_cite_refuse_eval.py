"""8.4 citations, refuse, evals. Fixture models only."""

import inspect

from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.rag.cite import format_sources
from eval.runners.rag_metrics import QUESTIONS, load_questions, render, run_metrics
from tests.fixtures.fake_model import FakeChatModel

PROCEDURES = (
    "dataflow/knowledge_base/internal_operations/support_operations/"
    "customer_support_procedures.markdown"
)


def test_reply_names_real_file(monkeypatch):
    monkeypatch.setattr(
        "dataflow.graphs.rag_graph.retrieve_passages",
        lambda *args, **kwargs: [
            {
                "text": "Agent (Level 1): Approve refunds under 30 days for Starter/Professional.",
                "source": PROCEDURES,
                "folder": "internal_operations",
                "heading_path": (
                    "6. Refund and Cancellation Procedures > 6.1 Authorization Levels"
                ),
                "h2": "6. Refund and Cancellation Procedures",
                "h3": "6.1 Authorization Levels",
                "score": 0.1,
            }
        ],
    )
    model = FakeChatModel(
        route="retrieve",
        reply="An agent can approve a refund under 30 days.",
        structured={
            "Grade": {
                "label": "keep",
                "reason": "authorization levels for a customer refund",
            }
        },
    )
    graph = build_rag_graph(model=model, max_rewrites=0)
    out = graph.invoke({"question": "Who can approve a refund under 30 days?"})
    assert "customer_support_procedures.markdown" in out["reply"].replace("\\", "/")
    assert "Sources:" in out["reply"]
    assert "6.1 Authorization Levels" in out["reply"]


def test_chitchat_cites_nothing():
    graph = build_rag_graph(
        model=FakeChatModel(route="answer", reply="You are welcome.")
    )
    out = graph.invoke({"question": "Thanks, that fixed it."})
    assert "Sources: none" in out["reply"]


def test_refuse_on_empty_after_one_rewrite(monkeypatch):
    monkeypatch.setattr(
        "dataflow.graphs.rag_graph.retrieve_passages",
        lambda *args, **kwargs: [],
    )
    graph = build_rag_graph(
        model=FakeChatModel(
            route="retrieve",
            reply="student discount enterprise plan",
        ),
        max_rewrites=1,
    )
    out = graph.invoke(
        {"question": "Do you offer a student discount on the Enterprise plan?"}
    )
    assert "I do not have that in the knowledge base" in out["reply"]
    assert int(out.get("rewrites") or 0) == 1
    assert "Sources:\n" not in out["reply"]


def test_force_generate_flag_is_off_by_default():
    default = inspect.signature(build_rag_graph).parameters["force_generate_on_empty"]
    assert default.default is False


def test_eval_file_has_all_four_kinds():
    rows = load_questions(QUESTIONS)
    kinds = {str(row.get("kind") or "") for row in rows}
    assert kinds == {"policy", "lookup", "refuse", "paraphrase"}
    counts = {kind: 0 for kind in kinds}
    for row in rows:
        counts[str(row["kind"])] += 1
    assert counts["policy"] == 4
    assert counts["lookup"] == 2
    assert counts["refuse"] == 3
    assert counts["paraphrase"] == 3
    assert len(rows) == 12


def test_metrics_runner_smoke():
    def naive(question: str) -> dict:
        lower = question.lower()
        if any(word in lower for word in ("coffee", "gym", "lifetime", "warranty")):
            return {
                "answer": "Yes, students get 20 percent off the Enterprise plan.",
                "sources": [],
                "passages": [],
                "refused": False,
                "route": "naive",
            }
        return {
            "answer": "The customer return window is 30 days from delivery.",
            "sources": [{"source": "dataflow/wiki/return_policy.md"}],
            "passages": [
                {
                    "source": "dataflow/wiki/return_policy.md",
                    "text": "The customer return window is 30 days from delivery.",
                }
            ],
            "refused": False,
            "route": "naive",
        }

    def agentic(question: str) -> dict:
        lower = question.lower()
        if any(word in lower for word in ("coffee", "gym", "lifetime", "warranty")):
            return {
                "answer": (
                    "I do not have that in the knowledge base. "
                    f"I understood the question as: {question}. "
                    "You can rephrase it or ask to speak to a person."
                ),
                "sources": [],
                "passages": [],
                "refused": True,
                "route": "retrieve",
            }
        if "DF-1001" in question:
            return {
                "answer": "Order DF-1001 is delivered. Item: desk lamp.",
                "sources": [],
                "passages": [],
                "refused": False,
                "route": "lookup",
            }
        if "DF-1002" in question:
            return {
                "answer": "Order DF-1002 is in_transit. Item: USB-C hub.",
                "sources": [],
                "passages": [],
                "refused": False,
                "route": "lookup",
            }
        source = "dataflow/wiki/return_policy.md"
        if "shipping" in lower or "package" in lower:
            source = "dataflow/wiki/shipping.md"
        if "extra user" in lower:
            source = "dataflow/knowledge_base/business_data/billing_and_pricing.csv"
        if "refund" in lower or "p0" in lower:
            source = (
                "dataflow/knowledge_base/internal_operations/"
                "support_operations/customer_support_procedures.markdown"
            )
        return {
            "answer": "Grounded from the knowledge base.",
            "sources": [{"source": source}],
            "passages": [{"source": source, "text": "Grounded passage."}],
            "refused": False,
            "route": "retrieve",
        }

    def judge(answer: str, passages: list, model=None) -> int:
        if "20 percent" in answer:
            return 0
        return 1

    report = run_metrics(naive_fn=naive, agentic_fn=agentic, judge=judge)
    text = render(report)
    assert "FLUENT_MISS" in text
    assert "naive" in text
    assert "agentic" in text
    misses = [row for row in report["naive"] if row.get("fluent_miss")]
    assert len(misses) == 3


def test_format_sources_row_and_heading():
    text = format_sources(
        [
            {
                "source": "dataflow/knowledge_base/business_data/billing_and_pricing.csv",
                "row": 0,
            },
            {
                "source": PROCEDURES,
                "h2": "6. Refund and Cancellation Procedures",
                "h3": "6.1 Authorization Levels",
            },
        ]
    )
    assert "row 0" in text
    assert "6.1 Authorization Levels" in text
