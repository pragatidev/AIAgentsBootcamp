"""Lab 08.04.02 (25.2), format_sources typed by the student. A scripted tool model and fixed passages stand in for
the real ones here, and only here."""

import importlib
import runpy
from pathlib import Path

import pytest

from langchain_core.messages import AIMessage

import config
from tests.fixtures.fake_model import FakeToolModel
from tests.fixtures.lab_copy import lab_copy

CI = importlib.import_module("dataflow.rag.cite")
RT = importlib.import_module("dataflow.tools.retrieve")
LAB = Path(__file__).resolve().parents[1] / "labs" / "08_04_02_print_citations.py"
PROCEDURES = {"text": "Agent (Level 1): Approve refunds under 30 days.", "source": "dataflow/knowledge_base/internal_operations/support_operations/customer_support_procedures.markdown", "folder": "internal_operations", "heading_path": "6. Refund and Cancellation Procedures > 6.1 Authorization Levels", "row": None, "line_start": 160, "line_end": 168}
PRICE = {"text": "Notes: Additional users: $10/user/month (Professional).", "source": "dataflow/knowledge_base/business_data/billing_and_pricing.csv", "folder": "business_data", "heading_path": "", "row": 0}
POLICY = {"text": "Returns are allowed within 30 days of delivery.", "source": "dataflow/wiki/return_policy.md", "folder": "wiki", "heading_path": "DataFlow return policy", "row": None}


REFUND, EXTRA = "Who can approve a refund under 30 days?", "How much does an extra user cost on the Professional plan?"


def _by_scope(question, k=3, folder=None, *, scope="customer", store=None, mode=None):
    """What the retrieve tool returns here: the scope decides, as it does in the module."""
    if scope != "support_agent":
        return [dict(POLICY)]
    return [dict(PRICE)] if "extra user" in question else [dict(PROCEDURES), dict(POLICY)]


def _script():
    def call(question, cid):
        return AIMessage(content="", tool_calls=[{"name": "retrieve", "args": {"question": question}, "id": cid, "type": "tool_call"}])

    return [call(REFUND, "c1"), AIMessage(content="A Level 1 agent."), call(REFUND, "c2"), AIMessage(content="I cannot see that."), call(EXTRA, "c3"), AIMessage(content="Ten dollars.")]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeToolModel(script=_script()))
    monkeypatch.setattr(RT, "retrieve_passages", _by_scope)


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


def test_the_desk_cites_every_passage_the_tool_returned(capsys):
    # No grade on the create_agent desk: the support lead's Sources block holds both returned passages.
    out = _out(LAB, capsys)
    staff = out[out.index("desk support_agent actor desk-lead") : out.index("desk customer actor anon")]
    assert "tool_call retrieve {'question': 'Who can approve a refund under 30 days?'}" in staff
    assert staff[-3:] == ["Sources:", PROCEDURES["source"] + " > 6. Refund and Cancellation Procedures > 6.1 Authorization Levels", POLICY["source"] + " > DataFlow return policy"]
    customer = out[out.index("desk customer actor anon") : out.index("customer_desk_cites_internal False")]
    assert customer[-2:] == ["Sources:", POLICY["source"] + " > DataFlow return policy"]


def test_one_refund_citation_ends_in_its_lines(capsys):
    out = _out(LAB, capsys)
    assert "refund_citation_with_lines " + PROCEDURES["source"] + " > 6. Refund and Cancellation Procedures > 6.1 Authorization Levels lines 160 to 168" in out


def test_the_lab_imports_no_graph():
    from tests.fixtures.lab_imports import graph_imports

    assert graph_imports(LAB) == []


def test_the_break_loses_row_0(tmp_path, capsys):
    broken = lab_copy(LAB, tmp_path, '        if row is not None and row != "":\n', "        if row:\n")
    out = _out(broken, capsys)
    assert PRICE["source"] in out and PRICE["source"] + " row 0" not in out
    assert "price_cites_a_row False" in out
