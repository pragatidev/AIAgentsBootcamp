"""v1 drawing. Invoke and classify live in test_dataflow_v1.py."""

from dataflow.graphs.v1_triage import build_v1_triage


def test_v1_line_is_in_the_drawing():
    text = build_v1_triage().get_graph().draw_mermaid()
    assert "classify" in text
    assert "lookup" in text
    assert "reply" in text
