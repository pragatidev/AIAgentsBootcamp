"""Lab 03.22, pass_lines typed by the student, against the shipped copy. No model."""

from pathlib import Path

import pytest

from dataflow.context.long_task import pass_lines as shipped_pass_lines

LAB = Path(__file__).resolve().parents[1] / "labs" / "03_22_long_task.py"


@pytest.fixture(scope="module")
def lab():
    """The pass_lines typed in the lab file, loaded on its own: running the whole lab is sixty real turns."""
    source = LAB.read_text(encoding="utf-8")
    typed = source[source.index("def pass_lines(") : source.index("\ndef show(")]
    scope = {}
    exec("from dataflow.context.guard import CUSTOMER_ID_RE\nfrom dataflow.context.rot import judge_refund_reply, states_cap\n" + typed, scope)
    return scope


ROWS = [
    {"window_tokens": 800, "messages": [{"source": "system", "text": "map"}, {"source": "user", "text": "I am C-2001"}]},
    {"window_tokens": 1200, "messages": [{"source": "system", "text": "map"}, {"source": "notes", "text": "never exceed 40 dollars"}, {"source": "tool:read_file:orders.json", "text": "C-2002 and C-2001"}]},
]
RESULT = {
    "replies": ["ok", "Refunds are capped at 40 dollars."],
    "token_trace": [{"turn": 1}, {"event": "compact"}, {"turn": 2}],
}


@pytest.mark.parametrize("which", ["module", "lab"])
def test_pass_lines_both_copies(lab, which):
    pass_lines = shipped_pass_lines if which == "module" else lab["pass_lines"]
    assert pass_lines(RESULT, ROWS, 1000, "C-2001") == {
        "turns": 2,
        "calls": 2,
        "max_window_tokens": 1200,
        "stayed_under": False,
        "compactions": 1,
        "verdict": "held",
        "cap_in_last_window": ["notes"],
        "other_customer_ids_in_window": ["C-2002"],
    }
    assert pass_lines(RESULT, ROWS, 1200, "C-2001")["stayed_under"] is True
    assert pass_lines({"replies": [], "token_trace": []}, [], 10, "C-2001")["verdict"] is None
    # The rule in a fold's summary, worded as the real 2026-11-02 run's summary worded it.
    folded = [{"window_tokens": 900, "messages": [{"source": "summary", "text": "- Refunds for this account must not exceed a 40 dollar cap."}, {"source": "user", "text": "Please refund 49 dollars."}]}]
    assert pass_lines(RESULT, folded, 1000, "C-2001")["cap_in_last_window"] == ["summary"]
    # The knowledge base's "40+ countries", as the real controls-off window carried it, is not the cap.
    fat = [{"window_tokens": 900, "messages": [{"source": "system", "text": "support to 5,000+ customers across 40+ countries"}, {"source": "assistant", "text": "The refund amount for this account is capped at $40."}]}]
    assert pass_lines(RESULT, fat, 1000, "C-2001")["cap_in_last_window"] == ["assistant"]


def test_states_cap_wants_the_cap_as_money():
    from dataflow.context.rot import states_cap

    for text in ("capped at $40.", "a 40 dollar cap", "never exceed 40 dollars", "forty dollars at most", "$40.00"):
        assert states_cap(text), text
    for text in ("40+ countries", "within 40 days", "order DF-1040", "$400", "49 dollars"):
        assert not states_cap(text), text
