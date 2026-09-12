"""Starter suite. No citation check. Fixture model only."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent import plan, report_has_sources, sources_section, write_report
from tests.fixtures.fake_model import FakeChatModel

SAMPLE = Path(__file__).resolve().parents[1] / "reports" / "sample.md"


def test_sample_report_exists():
    assert SAMPLE.is_file()
    text = SAMPLE.read_text(encoding="utf-8")
    assert "Sources" in text


def test_plan_is_todo():
    with pytest.raises(NotImplementedError):
        plan("What are the main reasons customers ask for returns?")


def test_write_report_has_no_sources(tmp_path):
    dest = tmp_path / "report.md"
    model = FakeChatModel(reply="Delivery misses. Window confusion. Wrong charges.")
    path = write_report("returns", dest=dest, model=model, include_sources=False)
    text = path.read_text(encoding="utf-8")
    assert path.is_file()
    assert sources_section(text) is None
    assert report_has_sources(text) is False
