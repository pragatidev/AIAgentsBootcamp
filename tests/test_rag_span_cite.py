"""Citations that open to the lines (25.7). Known answers read from the files themselves. No model, no Ollama."""

import inspect

from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.rag.chunk import chunk_by_heading, chunk_recursive, line_span
from dataflow.rag.cite import format_sources, support_spans
from dataflow.rag.load import KB_DIR, load_knowledge_base
from tests.fixtures.fake_model import FakeChatModel

PROCEDURES = KB_DIR / "internal_operations" / "support_operations" / "customer_support_procedures.markdown"
GUIDE = KB_DIR / "customer_facing" / "troubleshooting_guide.txt"


def _file_lines(path):
    return path.read_text(encoding="utf-8").split("\n")


def test_line_span_known_answer():
    text = "one\ntwo\nthree\nfour\n"
    assert line_span(text, 0, 3) == (1, 1)
    assert line_span(text, 4, 9) == (2, 3)
    assert line_span(text, text.index("four"), 4) == (4, 4)


def test_heading_chunk_lines_point_at_its_heading():
    chunks = chunk_by_heading(load_knowledge_base(roots=(PROCEDURES,)))
    refund = next(c for c in chunks if c.metadata.get("h3") == "6.1 Authorization Levels")
    lines = _file_lines(PROCEDURES)
    start, end = refund.metadata["line_start"], refund.metadata["line_end"]
    assert lines[start - 1] == "### 6.1 Authorization Levels"
    last_body_line = refund.page_content.splitlines()[-1].strip()
    assert lines[end - 1].strip() == last_body_line
    assert PROCEDURES.read_text(encoding="utf-8")[refund.metadata["start_index"]:].startswith("### 6.1 Authorization Levels")


def test_every_markdown_chunk_in_the_corpus_has_a_span():
    chunks = chunk_by_heading(load_knowledge_base())
    text_chunks = [c for c in chunks if str(c.metadata.get("source", "")).endswith((".md", ".markdown", ".txt"))]
    assert text_chunks and all(c.metadata.get("line_start") for c in text_chunks)
    assert all(c.metadata["line_start"] <= c.metadata["line_end"] for c in text_chunks)


def test_recursive_chunk_start_index_round_trips():
    docs = load_knowledge_base(roots=(GUIDE,))
    text = docs[0].page_content
    for chunk in chunk_recursive(docs, chunk_size=1000):
        start = chunk.metadata["start_index"]
        assert text[start:].startswith(chunk.page_content)
        assert chunk.metadata["line_start"] == text.count("\n", 0, start) + 1


def test_csv_rows_carry_no_line_span():
    rows = chunk_by_heading(load_knowledge_base(roots=(KB_DIR / "business_data" / "billing_and_pricing.csv",)))
    assert rows and not any("line_start" in r.metadata for r in rows)


def test_format_sources_prints_lines():
    text = format_sources([{"source": "dataflow/wiki/return_policy.md", "heading_path": "DataFlow return policy", "line_start": 3, "line_end": 5}])
    assert text == "dataflow/wiki/return_policy.md > DataFlow return policy lines 3 to 5"


def test_unsupported_sentence_flagged():
    passages = [{"source": "dataflow/wiki/return_policy.md", "text": "Returns are allowed within 30 days of delivery when the item is unused.", "line_start": 3, "line_end": 3}]
    claims = support_spans("Returns are allowed within 30 days of delivery. Every lamp has a lifetime warranty.", passages)
    assert [c["unsupported"] for c in claims] == [False, True]
    assert claims[0]["line_start"] == 3


def test_span_citations_off_by_default_and_on_when_asked(monkeypatch):
    assert inspect.signature(build_rag_graph).parameters["span_citations"].default is False
    passage = {"source": "dataflow/wiki/return_policy.md", "folder": "wiki", "heading_path": "DataFlow return policy", "text": "Returns are allowed within 30 days of delivery.", "line_start": 3, "line_end": 4, "start_index": 30}
    monkeypatch.setattr("dataflow.graphs.rag_graph.retrieve_passages", lambda *a, **k: [dict(passage)])
    reply = "Returns are allowed within 30 days of delivery. Every lamp has a lifetime warranty."
    plain = build_rag_graph(model=FakeChatModel(route="retrieve", reply=reply)).invoke({"question": "return window?"})
    assert " lines " not in plain["reply"] and "Claims:" not in plain["reply"]
    spans = build_rag_graph(model=FakeChatModel(route="retrieve", reply=reply), span_citations=True).invoke({"question": "return window?"})
    assert "dataflow/wiki/return_policy.md > DataFlow return policy lines 3 to 4" in spans["reply"]
    assert "UNSUPPORTED: Every lamp has a lifetime warranty." in spans["reply"]
