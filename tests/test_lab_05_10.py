"""Lab 05.10, TicketClass typed by the student. A scripted model stands in for the real one here, and only here."""

import runpy
import typing
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

import config
from techcorp.agent import schemas
from tests.fixtures.fake_model import FakeChatModel

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_10_structured_output_classifier.py"
FIVE = ("password", "access", "vpn", "software", "other")


class ScriptedClassifier:
    """with_structured_output answers by keyword (the fixture router); create_agent gets one TicketClass tool call."""

    model = "scripted"

    def with_structured_output(self, schema, **kwargs):
        return FakeChatModel().with_structured_output(schema, **kwargs)

    def bind_tools(self, tools, **kwargs):
        return self

    def bind(self, **kwargs):
        return self

    def invoke(self, messages, **kwargs):
        args = {"category": "vpn", "priority": "normal", "needs_human": True, "reason": "VPN drops"}
        return AIMessage(content="", tool_calls=[{"name": "TicketClass", "args": args, "id": "s1", "type": "tool_call"}])


@pytest.fixture(scope="module")
def run():
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "get_chat_model", lambda **kw: ScriptedClassifier())
    import contextlib
    import io

    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            lab = runpy.run_path(str(LAB), run_name="__main__")
    finally:
        mp.undo()
    return lab, buffer.getvalue().splitlines()


def test_lab_form_matches_package(run):
    lab, _ = run
    assert lab["TicketClass"].model_json_schema() == schemas.TicketClass.model_json_schema()


def test_category_list_is_the_five(run):
    lab, out = run
    for cls in (lab["TicketClass"], schemas.TicketClass):
        assert typing.get_args(cls.model_fields["category"].annotation) == FIVE
    assert out[0] == "category_values " + str(list(FIVE))


def test_lab_scores_its_rows(run):
    _, out = run
    rows = [line for line in out if line.startswith("row ")]
    assert len(rows) == 5 and all(" TicketClass " in row for row in rows)
    assert "categories_right 4/4" in out


def test_response_format_lands_in_structured_response(run):
    lab, out = run
    assert out[-1].startswith("structured_response TicketClass category='vpn'")
    assert isinstance(lab["out"]["structured_response"], lab["TicketClass"])
