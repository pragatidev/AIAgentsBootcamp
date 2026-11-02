"""Coding exercise 5.20 starter. A compaction step that passes a token budget test.

Write fit_to_budget(messages, budget, summarise):
  - count with count_tokens; at or under the budget, return the messages unchanged
  - over it, keep the first message (the system message) and the last message (the newest user
    turn) word for word, and replace everything between them with one assistant message whose
    content is "SUMMARY\\n" followed by summarise(text), where text is those messages joined as
    "role: content" lines
  - still over the budget after that, raise OverBudget instead of sending

Test it: python -m pytest tests/test_ex_token_budget.py -q
"""

from dataflow.context.agent import count_tokens


class OverBudget(Exception):
    """The messages cannot be folded under the budget."""


def fit_to_budget(messages: list, budget: int, summarise) -> list:
    # TODO: fold the middle of the conversation until it fits, or raise OverBudget
    raise NotImplementedError
