"""8.3 agentic RAG graph and corrective policy. Fixture models only."""

import pytest

from dataflow.graphs.crag import MAX_REWRITES, after_grade, widen
from dataflow.graphs.rag_graph import (
    build_rag_graph,
    generate,
    grade,
    refuse,
)
from tests.fixtures.fake_model import FakeChatModel

HANDBOOK = {
    "text": "Return equipment within 30 days of termination. Damaged/lost equipment may incur fees.",
    "source": "dataflow/knowledge_base/internal_operations/hr_policies/employee_handbook.txt",
    "folder": "internal_operations",
}
POLICY = {
    "text": "The customer return window is 30 days from delivery. Returns are allowed within 30 days of delivery when the item is unused.",
    "source": "dataflow/wiki/return_policy.md",
    "folder": "wiki",
}


def test_route_lookup_for_order_id():
    graph = build_rag_graph(model=FakeChatModel(route="lookup"))
    out = graph.invoke({"question": "Where is order DF-1001?"})
    assert out["route"] == "lookup"
    assert out["order"]["found"] is True
    assert out["order"]["order_id"] == "DF-1001"
    assert "DF-1001" in out["reply"]
    drawing = graph.get_graph().draw_mermaid()
    assert "retrieve" in drawing
    assert "refuse" in drawing


def test_grade_drops_handbook():
    model = FakeChatModel(
        structured={
            "Grade": [
                {
                    "label": "wrong",
                    "reason": "This is an HR equipment return, not a customer return.",
                },
                {
                    "label": "keep",
                    "reason": "This is the customer return window.",
                },
            ]
        }
    )
    out = grade(
        {
            "question": "Can I send back an unused lamp after twelve days?",
            "passages": [HANDBOOK, POLICY],
        },
        model=model,
    )
    assert out["grades"][0]["label"] == "wrong"
    assert "employee_handbook" in out["grades"][0]["source"]
    assert len(out["graded"]) == 1
    assert out["graded"][0]["source"] == POLICY["source"]


def test_rewrite_once_then_refuse(monkeypatch):
    monkeypatch.setattr(
        "dataflow.graphs.rag_graph.retrieve_passages",
        lambda *args, **kwargs: [],
    )
    model = FakeChatModel(
        route="retrieve",
        reply="return window unused item thirty days",
    )
    graph = build_rag_graph(model=model, max_rewrites=1)
    out = graph.invoke(
        {"question": "Can I send back an unused lamp after twelve days?"}
    )
    assert out["route"] == "retrieve"
    assert int(out.get("rewrites") or 0) == 1
    assert "I do not have that in the knowledge base" in out["reply"]
    assert out.get("sources") == []


def test_generate_only_from_kept():
    model = FakeChatModel(reply="You have 30 days from delivery when the item is unused.")
    out = generate(
        {
            "question": "Can I send back an unused lamp after twelve days?",
            "graded": [POLICY],
            "passages": [HANDBOOK, POLICY],
        },
        model=model,
    )
    sources = " ".join(str(row.get("source") or "") for row in out["sources"])
    assert POLICY["source"] in sources
    assert "employee_handbook" not in sources
    assert out["answer"]


def test_after_grade_policy():
    rows = [
        ({"grades": [{"label": "keep"}], "rewrites": 0}, False, "generate"),
        ({"grades": [{"label": "wrong"}], "rewrites": 0}, False, "rewrite"),
        ({"grades": [{"label": "wrong"}], "rewrites": 1}, False, "refuse"),
        ({"grades": [{"label": "wrong"}], "rewrites": 1}, True, "widen"),
    ]
    for state, allowed, expected in rows:
        assert (
            after_grade(
                state,
                max_rewrites=MAX_REWRITES,
                web_search_allowed=allowed,
            )
            == expected
        )


def test_widen_off_by_default():
    assert (
        after_grade(
            {"grades": [{"label": "drop"}], "rewrites": 1},
            web_search_allowed=False,
        )
        == "refuse"
    )
    with pytest.raises(NotImplementedError, match="web search is a company policy"):
        widen({"question": "anything"}, web_search_allowed=False)
    graph = build_rag_graph(model=FakeChatModel(route="lookup"))
    drawing = graph.get_graph().draw_mermaid()
    assert "widen" in drawing


def test_refuse_text():
    out = refuse({"question": "Do you offer a student discount?"})
    assert "I do not have that in the knowledge base" in out["reply"]
    assert "student discount" in out["reply"]
    assert out["sources"] == []


# R4 (24.3, 24.5, 25.4): the hooks a lab plugs its own copy into, and widen once inside the scope.

import importlib  # noqa: E402

from dataflow.graphs.crag import should_refuse  # noqa: E402

RT = importlib.import_module("dataflow.tools.retrieve")

DROP = {"label": "drop", "reason": "fixture drop"}


def _stub_retrieve(monkeypatch, rows):
    stub = lambda *args, **kwargs: [dict(r) for r in rows]  # noqa: E731
    monkeypatch.setattr("dataflow.graphs.rag_graph.retrieve_passages", stub)
    monkeypatch.setattr(RT, "retrieve_passages", stub)


def test_should_refuse_rows():
    rows = [
        ({"grades": [{"label": "keep"}], "rewrites": 0}, False),
        ({"passages": [POLICY] * 3, "grades": [DROP] * 3, "rewrites": 0}, False),
        ({"passages": [POLICY] * 3, "grades": [DROP] * 3, "rewrites": 1}, True),
        ({"passages": [], "grades": [], "rewrites": 1}, True),
        ({"grades": [], "graded": [POLICY], "rewrites": 1}, False),
    ]
    for state, expected in rows:
        assert should_refuse(state, max_rewrites=MAX_REWRITES) is expected


def test_grade_fn_hook_runs_the_labs_grade(monkeypatch):
    _stub_retrieve(monkeypatch, [POLICY])
    seen = []

    def lab_grade(state, runtime=None, *, model=None):
        seen.append(len(state.get("passages") or []))
        return {"grades": [{"source": POLICY["source"], "label": "keep", "reason": "lab", "text": POLICY["text"]}], "graded": [POLICY]}

    out = build_rag_graph(model=FakeChatModel(route="retrieve", reply="30 days."), grade_fn=lab_grade).invoke({"question": "return window?"})
    assert seen == [1] and out["grades"][0]["reason"] == "lab"


def test_policy_hook_drives_the_edge(monkeypatch):
    _stub_retrieve(monkeypatch, [POLICY])
    calls = []

    def lab_policy(state, *, max_rewrites, web_search_allowed):
        calls.append(max_rewrites)
        return "refuse"

    out = build_rag_graph(model=FakeChatModel(route="retrieve"), policy=lab_policy).invoke({"question": "return window?"})
    assert calls == [MAX_REWRITES] and out["reply"].startswith("I do not have that in the knowledge base")


def test_refuse_check_that_reads_the_retrieve_generates_on_rejected_passages(monkeypatch):
    _stub_retrieve(monkeypatch, [HANDBOOK, POLICY])

    def reads_the_retrieve(state, *, max_rewrites):
        return not state.get("passages") and int(state.get("rewrites") or 0) >= max_rewrites

    fake = FakeChatModel(route="retrieve", reply=["rewritten question", "An answer anyway."], structured={"Grade": DROP})
    out = build_rag_graph(model=fake, refuse_check=reads_the_retrieve).invoke({"question": "Do you sell coffee beans?"})
    assert not out["reply"].startswith("I do not have that")
    cited = [row["source"] for row in out["sources"]]
    assert HANDBOOK["source"] in cited
    fake = FakeChatModel(route="retrieve", reply=["rewritten question"], structured={"Grade": DROP})
    out = build_rag_graph(model=fake, refuse_check=should_refuse).invoke({"question": "Do you sell coffee beans?"})
    assert out["reply"].startswith("I do not have that in the knowledge base") and out["sources"] == []


def test_widen_stops(monkeypatch):
    _stub_retrieve(monkeypatch, [POLICY])
    fake = FakeChatModel(route="retrieve", reply=["rewritten question"], structured={"Grade": DROP})
    out = build_rag_graph(model=fake, web_search_allowed=True).invoke({"question": "Do you sell coffee beans?"}, {"recursion_limit": 30})
    assert out["widened"] is True
    assert out["reply"].startswith("I do not have that in the knowledge base")


def test_widen_keeps_the_callers_scope(monkeypatch):
    seen = {}

    def fake_retrieve(question, k=3, folder=None, *, scope="customer"):
        seen["scope"], seen["k"] = scope, k
        return []

    monkeypatch.setattr(RT, "retrieve_passages", fake_retrieve)
    assert widen({"question": "q"}, web_search_allowed=True) == {"passages": [], "widened": True}
    assert seen == {"scope": "customer", "k": 6}
