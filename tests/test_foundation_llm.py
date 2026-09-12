"""Section 2 helpers. Pytest stays green with no live model."""

from pathlib import Path

from langchain_core.messages import AIMessage

from src.part1 import TicketClass, parse_ticket, parse_tool_call_entry, run_desk

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


def test_tool_call_shape_parsed():
    raw = FIXTURE.read_text(encoding="utf-8")
    parsed = parse_tool_call_entry(raw)
    assert parsed["name"] == "reset_password"
    assert parsed["arguments"]["user_id"] == "E-4101"
    assert isinstance(parsed["arguments_json"], str)
    assert "E-4101" in parsed["arguments_json"]
    assert parsed["id"]


def test_model_swap_keeps_shape():
    class FixtureModel:
        def __init__(self, name: str) -> None:
            self.model = name

        def invoke(self, prompt: str):
            return AIMessage(
                content="an agent is a model in a loop with tools",
                usage_metadata={
                    "input_tokens": 8,
                    "output_tokens": 12,
                    "total_tokens": 20,
                },
            )

    one = run_desk(FixtureModel("qwen3:8b"), "what is an AI agent?")
    two = run_desk(FixtureModel("llama3.2:3b"), "what is an AI agent?")
    assert one["keys"] == two["keys"]
    assert one["keys"] == ["model", "content", "usage"]
    assert one["model"] != two["model"]
    assert one["content"]
    assert two["content"]
