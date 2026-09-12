"""10.3 load replay. p95 of a known list and a hung ticket. No Ollama."""

import re

from langchain_core.messages import AIMessage

from dataflow.tools.orders import lookup_order
from eval.load.replay import p95, run_replay
from tests.fixtures.fake_model import _last_tool_content, _messages_text


class _LookupThenAnswer:
    """Fixture model. Stateless so two tickets can share it."""

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, messages, **kwargs):
        if _last_tool_content(messages):
            return AIMessage(content="looked up the order")
        text = _messages_text(messages)
        match = re.search(r"DF-\d+", text.upper())
        order_id = match.group(0) if match else "DF-1001"
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "lookup_order",
                    "args": {"order_id": order_id},
                    "id": "call_lookup_" + order_id,
                    "type": "tool_call",
                }
            ],
        )


def test_p95_of_a_known_list():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert p95(values) == 10.0
    assert p95([4.0, 4.0, 4.0, 40.0]) == 40.0
    assert p95([]) == 0.0


def test_hung_ticket_marked_with_fixture_and_planted_sleep():
    rows = [
        {"id": "slow-lookup", "input": "Where is order DF-1001?"},
        {"id": "fast-lookup", "input": "Where is order DF-1002?"},
    ]
    report = run_replay(
        rows=rows,
        model=_LookupThenAnswer(),
        tools=[lookup_order],
        concurrency=2,
        timeout=1.0,
        slow_node=True,
        slow_seconds=4.0,
        progress=False,
    )
    statuses = {row["id"]: row["status"] for row in report["rows"]}
    assert statuses.get("slow-lookup") == "HUNG"
    assert "HUNG" in {row["status"] for row in report["rows"]}
    assert p95.__name__ == "p95"
