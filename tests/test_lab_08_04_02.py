"""Lab 08.04.02 (25.2), format_sources typed by the student. A scripted model and fixed passages stand in for the
real ones here, and only here."""

import importlib
import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs import rag_graph as G
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import lab_copy

CI = importlib.import_module("dataflow.rag.cite")
LAB = Path(__file__).resolve().parents[1] / "labs" / "08_04_02_print_citations.py"
PROCEDURES = {"text": "Agent (Level 1): Approve refunds under 30 days.", "source": "dataflow/knowledge_base/internal_operations/support_operations/customer_support_procedures.markdown", "folder": "internal_operations", "heading_path": "6. Refund and Cancellation Procedures > 6.1 Authorization Levels", "row": None}
PRICE = {"text": "Notes: Additional users: $10/user/month (Professional).", "source": "dataflow/knowledge_base/business_data/billing_and_pricing.csv", "folder": "business_data", "heading_path": "", "row": 0}
POLICY = {"text": "Returns are allowed within 30 days of delivery.", "source": "dataflow/wiki/return_policy.md", "folder": "wiki", "heading_path": "DataFlow return policy", "row": None}


def _all_folders(index, question, k=3, folder=None):
    return [dict(PRICE)] if "extra user" in question else [dict(PROCEDURES), dict(POLICY)]


def _keep_answers(messages):
    text = str(messages[-1]["content"])
    keep = "Approve refunds" in text or "Additional users" in text or ("return_policy" in text and "refund" in text.lower())
    return {"label": "keep" if keep else "drop", "reason": "fixture"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="retrieve", reply="An answer.", structured={"Grade": _keep_answers}))
    monkeypatch.setattr(G, "get_index", lambda *a, **k: object())
    monkeypatch.setattr(G, "search", _all_folders)
    monkeypatch.setattr(G, "retrieve_passages", lambda *a, **k: [dict(POLICY)])


SAMPLES = [
    [{"source": "dataflow/knowledge_base/business_data/billing_and_pricing.csv", "row": 0}],
    [{"source": "dataflow/wiki/return_policy.md", "h2": "Returns", "h3": "Window"}],
    [{"source": "dataflow/wiki/return_policy.md", "heading_path": "DataFlow return policy", "h2": "ignored"}],
    ["  dataflow/wiki/shipping.md  "],
    [{}],
]


def _out(path, capsys):
    runpy.run_path(str(path), run_name="__main__")
    return capsys.readouterr().out.splitlines()


@pytest.mark.parametrize("sample", SAMPLES)
def test_typed_format_sources_matches_the_module(sample):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    assert lab["format_sources"](sample) == CI.format_sources(sample)


def test_three_desks(capsys):
    out = _out(LAB, capsys)
    assert PROCEDURES["source"] + " > 6. Refund and Cancellation Procedures > 6.1 Authorization Levels" in out
    assert "customer_desk_cites_internal False" in out
    assert PRICE["source"] + " row 0" in out and "price_cites_a_row True" in out


def test_the_break_loses_row_0(tmp_path, capsys):
    broken = lab_copy(LAB, tmp_path, '        if row is not None and row != "":\n', "        if row:\n")
    out = _out(broken, capsys)
    assert PRICE["source"] in out and PRICE["source"] + " row 0" not in out
    assert "price_cites_a_row False" in out
