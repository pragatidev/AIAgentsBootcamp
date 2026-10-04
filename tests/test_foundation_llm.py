"""Section 2 helpers. Pytest stays green with no live model."""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from src.part1 import (
    ImpossibleTicket,
    TicketClass,
    parse_ticket,
    parse_tool_call_entry,
    run_desk,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "raw_tool_calls.json"


def test_structured_output_parses_with_fixture():
    raw = (
        '{"category": "password", "priority": "high", '
        '"user_id": "E-4101", "summary": "reset laptop password"}'
    )
    obj = parse_ticket(raw, TicketClass)
    assert obj.user_id == "E-4101"
    assert obj.category == "password"
    assert obj.priority == "high"


def test_ticket_reply_fails_the_impossible_schema():
    # Lab 2.8's break: a valid TicketClass reply checked against ImpossibleTicket.
    raw = (
        '{"category": "password", "priority": "high", '
        '"user_id": "E-4101", "summary": "reset laptop password"}'
    )
    with pytest.raises(ValidationError) as caught:
        parse_ticket(raw, ImpossibleTicket)
    errors = caught.value.errors()
    assert [(e["loc"], e["type"]) for e in errors] == [(("planet",), "missing")]


def test_tool_call_shape_parsed():
    raw = FIXTURE.read_text(encoding="utf-8")
    parsed = parse_tool_call_entry(raw)
    assert parsed["name"] == "reset_password"
    assert parsed["arguments"]["user_id"] == "E-4101"
    assert isinstance(parsed["arguments_json"], str)
    assert "E-4101" in parsed["arguments_json"]
    assert parsed["id"]


class FixtureModel:
    def __init__(self, name: str, content: str = "an agent is a model in a loop with tools", usage=True) -> None:
        self.model = name
        self.content = content
        self.usage = usage

    def invoke(self, prompt: str):
        usage = {"input_tokens": 8, "output_tokens": 12, "total_tokens": 20}
        return AIMessage(content=self.content, usage_metadata=usage if self.usage else None)


def test_model_swap_keeps_shape():
    one = run_desk(FixtureModel("qwen3:8b"), "what is an AI agent?")
    two = run_desk(FixtureModel("llama3.2:3b"), "what is an AI agent?")
    assert one["keys"] == two["keys"]
    assert one["keys"] == [
        "model",
        "content",
        "usage",
        "usage.input_tokens",
        "usage.output_tokens",
        "usage.total_tokens",
    ]
    assert one["model"] != two["model"]


def test_model_swap_check_fails_when_the_shape_differs():
    # The same_shape check is read from each run, so a model that sends no usage
    # and an empty reply is caught.
    one = run_desk(FixtureModel("qwen3:8b"), "what is an AI agent?")
    two = run_desk(FixtureModel("tiny:1b", content="", usage=False), "what is an AI agent?")
    assert two["keys"] == ["model"]
    assert (one["keys"] == two["keys"]) is False
