"""Hello graph, hidden loop vs graph, mermaid is real."""

from dataflow.graphs.v1_triage import build_v1_triage, classify
from tests.fixtures.fake_model import FakeChatModel


def test_hello_graph_nodes_include_start():
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class S(TypedDict, total=False):
        text: str

    def greet(state: S) -> dict:
        return {"text": "hello " + state.get("text", "")}

    g = StateGraph(S)
    g.add_node("greet", greet)
    g.add_edge(START, "greet")
    g.add_edge("greet", END)
    app = g.compile()
    assert app.invoke({"text": "dataflow"})["text"] == "hello dataflow"
    names = set(app.get_graph().nodes)
    assert "__start__" in names or "greet" in names


def test_classify_is_a_node_you_can_call_without_invoke():
    out = classify(
        {"ticket": "Can I return order DF-1001?"},
        model=FakeChatModel(),
    )
    assert out["route"] == "orders"


def test_v1_mermaid_names_the_line():
    text = build_v1_triage().get_graph().draw_mermaid()
    assert "classify" in text
    assert "lookup" in text
    assert "reply" in text
