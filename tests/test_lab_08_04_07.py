"""Lab 08.04.07 (25.7), line_span typed by the student. A scripted model and the real refund chunk stand in for the
model and the index here, and only here."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs import rag_graph as G
from dataflow.rag.chunk import chunk_by_heading
from dataflow.rag.chunk import line_span as module_line_span
from dataflow.rag.faiss_index import _row_payload
from dataflow.rag.load import KB_DIR, load_knowledge_base
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "08_04_07_span_citations.py"
PROCEDURES = KB_DIR / "internal_operations" / "support_operations" / "customer_support_procedures.markdown"
REFUND = next(c for c in chunk_by_heading(load_knowledge_base(roots=(PROCEDURES,))) if c.metadata.get("h3") == "6.1 Authorization Levels")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    model = FakeChatModel(route="retrieve", reply="An Agent (Level 1) can approve refunds under 30 days.", structured={"Grade": {"label": "keep", "reason": "k"}})
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    monkeypatch.setattr(G, "get_index", lambda *a, **k: object())
    monkeypatch.setattr(G, "search", lambda *a, **k: [_row_payload(REFUND, 0.4)])


def _out(path, capsys):
    namespace = runpy.run_path(str(path), run_name="__main__")
    return namespace, capsys.readouterr().out.splitlines()


def test_lines_cited_and_the_plant_flagged(capsys):
    _, out = _out(LAB, capsys)
    first, last = REFUND.metadata["line_start"], REFUND.metadata["line_end"]
    assert "lines_match True" in out
    assert f"refund_chunk_lines {first} to {last}" in out
    assert f"{first:4d} | ### 6.1 Authorization Levels" in out
    assert any(line.endswith(f"6.1 Authorization Levels lines {first} to {last}") for line in out)
    assert "UNSUPPORTED: Every desk lamp has a lifetime warranty." in out
    assert "planted_flagged True" in out


@pytest.mark.parametrize("start, length", [(0, 3), (4, 9), (120, 400), (17000, 200)])
def test_typed_line_span_matches_the_module(capsys, start, length):
    lab, _ = _out(LAB, capsys)
    text = PROCEDURES.read_text(encoding="utf-8")
    assert lab["line_span"](text, start, length) == module_line_span(text, start, length)


def test_the_break_is_off_by_one(tmp_path, capsys):
    broken = LAB.read_text(encoding="utf-8").replace('count("\\n", 0, start) + 1', 'count("\\n", 0, start)').replace(
        'count("\\n", 0, start + max(length, 1) - 1) + 1', 'count("\\n", 0, start + max(length, 1) - 1)'
    )
    copy = lab_copy(LAB, tmp_path, LAB.read_text(encoding="utf-8"), broken)
    _, out = _out(copy, capsys)
    assert "lines_match False" in out
