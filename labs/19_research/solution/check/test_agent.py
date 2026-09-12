"""Filled research agent. Citation check. Fixture model only."""

from __future__ import annotations

from agent import (
    isolated_subagent,
    plan,
    report_has_sources,
    write_files,
    write_report,
)
from tests.fixtures.fake_model import FakeChatModel


def test_plan_filled():
    rows = plan("returns")
    assert len(rows) >= 3
    assert any("source" in row["content"] for row in rows)


def test_isolated_reader_declared():
    reader = isolated_subagent("reader")
    assert reader.get("name") == "reader"


def test_write_files(tmp_path):
    path = write_files(tmp_path, "/notes.md", "fixture notes\n")
    assert path.is_file()
    assert "fixture notes" in path.read_text(encoding="utf-8")


def test_sourced_report_passes_citation_check(tmp_path):
    dest = tmp_path / "report.md"
    model = FakeChatModel(reply="Delivery misses. Window confusion. Wrong charges.")
    path = write_report("returns", dest=dest, model=model, include_sources=True)
    text = path.read_text(encoding="utf-8")
    assert report_has_sources(text) is True


def test_empty_source_report_fails_citation_check(tmp_path):
    dest = tmp_path / "empty.md"
    model = FakeChatModel(reply="Delivery misses.")
    path = write_report("returns", dest=dest, model=model, include_sources=False)
    text = path.read_text(encoding="utf-8")
    assert report_has_sources(text) is False
