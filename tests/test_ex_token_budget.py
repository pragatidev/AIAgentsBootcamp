"""Coding exercise 5.20: the token budget test.

It runs on the starter in exercises/ex_token_budget.py, and is skipped until the starter is written.
It also runs on a reference fold, so the test itself is shown to be passable and to bite.
"""

import pytest

from dataflow.context.agent import count_tokens
from exercises import ex_token_budget
from exercises.ex_token_budget import OverBudget


def reference_fit(messages: list, budget: int, summarise) -> list:
    if count_tokens(messages) <= budget:
        return messages
    middle = messages[1:-1]
    text = "\n".join(f"{m['role']}: {m['content']}" for m in middle)
    folded = [messages[0], {"role": "assistant", "content": "SUMMARY\n" + summarise(text)}, messages[-1]]
    if count_tokens(folded) > budget:
        raise OverBudget(count_tokens(folded))
    return folded


def conversation(turns: int = 12) -> list:
    messages = [{"role": "system", "content": "You are the DataFlow desk. Refunds never exceed 40 dollars."}]
    for i in range(turns):
        messages.append({"role": "user", "content": f"Question {i} about shipping, invoices and the lamp order DF-1001."})
        messages.append({"role": "assistant", "content": f"Answer {i}: here is what the policy says about that question."})
    messages.append({"role": "user", "content": "Please refund 49 dollars for the lamp."})
    return messages


def summarise(text: str) -> str:
    return "facts: order DF-1001. decisions: none."


@pytest.fixture(params=["reference", "yours"])
def fit(request):
    if request.param == "reference":
        return reference_fit
    try:
        ex_token_budget.fit_to_budget(conversation(1), 10**6, summarise)
    except NotImplementedError:
        pytest.skip("exercises/ex_token_budget.py is not written yet")
    return ex_token_budget.fit_to_budget


def test_under_the_budget_nothing_changes(fit):
    messages = conversation(2)
    assert fit(messages, count_tokens(messages), summarise) == messages


def test_over_the_budget_it_folds_under_it(fit):
    messages = conversation()
    budget = count_tokens(messages) // 3
    out = fit(messages, budget, summarise)
    assert count_tokens(out) <= budget
    assert out[0] == messages[0] and out[-1] == messages[-1]
    summaries = [m for m in out if str(m["content"]).startswith("SUMMARY\n")]
    assert len(summaries) == 1 and summaries[0]["role"] == "assistant"


def test_a_budget_below_the_system_message_raises(fit):
    with pytest.raises(OverBudget):
        fit(conversation(), 5, summarise)
