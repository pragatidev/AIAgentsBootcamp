"""The TechCorp parts the Section 4 labs type: their finished copies, each on a known answer. No live model."""

from __future__ import annotations

import json
import typing

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from techcorp.agent.by_hand import answer_calls, check_pairing
from techcorp.agent.desk import build_techcorp_desk, desk_summarizer, run_ticket
from techcorp.agent.evals import REFUSAL_SHAPE, load_cases, score_case
from techcorp.agent.prompts import SUMMARY_PROMPT
from techcorp.agent.resilience import is_transient, resilience
from techcorp.agent.schemas import TicketClass
from techcorp.agent.usage import TokenCounter, read_usage
from techcorp.tools import accounts as accounts_mod
from techcorp.tools.accounts import dummy_runtime, lookup_user
from tests.fixtures.fake_model import FailingChatModel, ScriptedToolChatModel


@pytest.fixture(autouse=True)
def audit_path(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts_mod, "AUDIT_PATH", path)
    return path


def _call(name: str, args: dict, call_id: str) -> dict:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


# 4.3 read_usage


def test_read_usage_known_answer():
    reply = AIMessage(
        content="Your reset is on its way. Ticket ID: TC-1001.",
        usage_metadata={"input_tokens": 58, "output_tokens": 182, "total_tokens": 240},
        additional_kwargs={"reasoning_content": "x" * 400},
    )
    assert read_usage(reply) == {
        "input_tokens": 58,
        "output_tokens": 182,
        "total_tokens": 240,
        "blocks": ["reasoning", "text"],
        "reasoning_chars": 400,
        "visible_words": 9,
    }


def test_read_usage_without_usage_is_zeros():
    out = read_usage(AIMessage(content="hi"))
    assert (out["input_tokens"], out["output_tokens"], out["total_tokens"]) == (0, 0, 0)
    assert out["blocks"] == ["text"] and out["reasoning_chars"] == 0


# 4.22 TokenCounter


def _usage_reply(content: str = "", tool_calls: list | None = None) -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=tool_calls or [],
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        response_metadata={"model_name": "scripted"},
    )


def test_token_counter_adds_every_model_call():
    from langchain_core.callbacks import UsageMetadataCallbackHandler

    model = ScriptedToolChatModel(
        script=[_usage_reply(tool_calls=[_call("lookup_user", {"query": "E-4101"}, "c1")]), _usage_reply("Done. TC-1001")]
    )
    desk = build_techcorp_desk(model=model, middleware=[])
    counter, builtin = TokenCounter(), UsageMetadataCallbackHandler()
    desk.invoke(
        {"messages": [HumanMessage(content="Ticket TC-1001: who am I?")]},
        config={"callbacks": [counter, builtin]},
    )
    assert (counter.calls, counter.input_tokens, counter.output_tokens, counter.total_tokens) == (2, 20, 10, 30)
    assert builtin.usage_metadata["scripted"]["total_tokens"] == 30
    assert counter.over(29) and not counter.over(30)


# 4.6 answer_calls and check_pairing


def test_answer_calls_answers_every_call_with_its_own_id():
    ai = AIMessage(content="", tool_calls=[_call("lookup_user", {"query": "E-4101"}, "c1"), _call("lookup_user", {"query": "Ben Ortiz"}, "c2")])
    answers = answer_calls(ai, dummy_runtime("E-4101"))
    assert [m.tool_call_id for m in answers] == ["c1", "c2"]
    assert json.loads(answers[1].content)["user_id"] == "E-4102"


def test_unknown_tool_is_a_typed_miss():
    ai = AIMessage(content="", tool_calls=[_call("delete_user", {"user_id": "E-4101"}, "c9")])
    assert json.loads(answer_calls(ai, dummy_runtime("E-4101"))[0].content) == {"found": False, "reason": "unknown tool delete_user"}


def test_envelope_wins_over_the_model_id():
    ai = AIMessage(content="", tool_calls=[_call("reset_password", {"user_id": "E-4102"}, "c3")])
    assert json.loads(answer_calls(ai, dummy_runtime("E-4101"))[0].content)["user_id"] == "E-4101"


def test_check_pairing_names_a_wrong_id_and_an_unanswered_call():
    ai = AIMessage(content="", tool_calls=[_call("lookup_user", {"query": "E-4101"}, "c1"), _call("lookup_user", {"query": "E-4102"}, "c2")])
    good = [ai, *answer_calls(ai, dummy_runtime("E-4101"))]
    assert check_pairing(good) == []
    wrong = [ai, ToolMessage(content="{}", tool_call_id="not-the-real-id"), good[2]]
    assert check_pairing(wrong) == ["unanswered call c1", "stray result not-the-real-id"]
    assert check_pairing([ai, good[1]]) == ["unanswered call c2"]


# 4.16 is_transient and resilience


class StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def _resilient_run(primary: FailingChatModel, fallback: ScriptedToolChatModel, stack: list | None = None) -> str:
    desk = build_techcorp_desk(model=primary, tools=[lookup_user], middleware=stack if stack is not None else resilience(fallback))
    out = desk.invoke({"messages": [HumanMessage(content="Ticket TC-1002: VPN?")]})
    return str(out["messages"][-1].content)


def test_is_transient():
    assert is_transient(ConnectionError("down")) and is_transient(StatusError(503))
    assert not any(is_transient(StatusError(code)) for code in (400, 401, 403, 404))


def test_one_transient_fault_is_one_retry_and_the_primary_answers():
    primary = FailingChatModel(error=ConnectionError("blip"), fail_times=1, script=[AIMessage(content="primary")])
    fallback = ScriptedToolChatModel(script=[AIMessage(content="fallback")])
    assert _resilient_run(primary, fallback) == "primary"
    assert (primary.raised, primary.calls, fallback.calls) == (1, 2, 0)


def test_a_404_skips_the_retries_and_the_fallback_answers():
    primary = FailingChatModel(error=lambda: StatusError(404), fail_times=-1, script=[AIMessage(content="primary")])
    fallback = ScriptedToolChatModel(script=[AIMessage(content="fallback")])
    assert _resilient_run(primary, fallback) == "fallback"
    assert primary.calls == 1 and fallback.calls == 1


def test_an_always_transient_fault_gets_two_retries_then_the_fallback():
    primary = FailingChatModel(error=lambda: ConnectionError("down"), fail_times=-1, script=[AIMessage(content="primary")])
    fallback = ScriptedToolChatModel(script=[AIMessage(content="fallback")])
    assert _resilient_run(primary, fallback) == "fallback"
    assert primary.calls == 3 and fallback.calls == 1


def test_retry_continue_hides_the_fallback():
    from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware

    primary = FailingChatModel(error=lambda: ConnectionError("down"), fail_times=-1, script=[AIMessage(content="primary")])
    fallback = ScriptedToolChatModel(script=[AIMessage(content="fallback")])
    stack = [ModelFallbackMiddleware(fallback), ModelRetryMiddleware(max_retries=2, retry_on=is_transient, initial_delay=0.0, jitter=False)]
    reply = _resilient_run(primary, fallback, stack)
    assert reply.startswith("Model call failed after 3 attempts with ConnectionError")
    assert fallback.calls == 0


# 4.18 score_case


def _state(*messages) -> dict:
    return {"messages": list(messages)}


def test_load_cases_has_the_three_cases():
    assert [c["case"] for c in load_cases()] == ["reset", "out_of_scope_monitor", "vpn_drops"]


def test_score_case_flags_reset_without_lookup():
    case = load_cases()[0]
    state = _state(
        AIMessage(content="", tool_calls=[_call("reset_password", {"user_id": "E-4101"}, "c1")]),
        AIMessage(content="Done. Your temporary password is abc. TC-1001"),
    )
    out = score_case(case, state)
    assert out["called"] == ["reset_password"] and out["order_ok"] is False and out["pass"] is False


def test_score_case_passes_a_shaped_refusal_and_rejects_an_unshaped_one():
    case = load_cases()[1]
    shaped = _state(AIMessage(content="I cannot help with that from the IT desk: we do not buy hardware. Please contact Procurement. TC-1099"))
    unshaped = _state(AIMessage(content="Sorry, we do not buy monitors here. TC-1099"))
    assert score_case(case, shaped)["pass"] is True
    assert score_case(case, unshaped)["refusal_ok"] is False
    assert REFUSAL_SHAPE.search("I cannot help with that from the IT desk: no. Please contact Network Support.")


# 4.15 desk_summarizer


def test_summary_prompt_has_messages_slot_and_the_secret_rule():
    assert "{messages}" in SUMMARY_PROMPT
    assert "Never copy a password" in SUMMARY_PROMPT


def test_desk_summarizer_folds_old_turns_into_one_summary():
    summarizer_model = ScriptedToolChatModel(script=[AIMessage(content="Employee id: E-4101\nTicket id: None\nDone: None\nStill open: None")])
    middleware = desk_summarizer(summarizer_model)
    assert middleware.summary_prompt == SUMMARY_PROMPT
    desk_model = ScriptedToolChatModel(script=[AIMessage(content="ok")])
    desk = build_techcorp_desk(model=desk_model, tools=[lookup_user], middleware=[middleware])
    history = []
    for n in range(3):
        history += [HumanMessage(content=f"turn {n}"), AIMessage(content=f"answer {n}")]
    out = desk.invoke({"messages": [*history, HumanMessage(content="turn 3")]})
    summaries = [m for m in out["messages"] if m.additional_kwargs.get("lc_source") == "summarization"]
    assert len(summaries) == 1 and "E-4101" in str(summaries[0].content)
    assert len(out["messages"]) <= 4


# 4.10 TicketClass


def test_category_list_is_the_five():
    annotation = TicketClass.model_fields["category"].annotation
    assert typing.get_args(annotation) == ("password", "access", "vpn", "software", "other")


def test_priority_has_bands():
    description = TicketClass.model_fields["priority"].description
    assert description.startswith("high:") and "normal:" in description and "low:" in description


# shared: run_ticket still runs on the summary-free gated desk


def test_run_ticket_on_the_scripted_desk_answers():
    desk = build_techcorp_desk(model=ScriptedToolChatModel(script=[AIMessage(content="Done. TC-1002")]))
    out = run_ticket(desk, "Ticket TC-1002: VPN?", user_id="E-4102")
    assert out["messages"][-1].content == "Done. TC-1002"
