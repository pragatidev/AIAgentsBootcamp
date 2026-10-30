# %%
"""Lab 4.18: iterate the TechCorp prompt against three tickets.

What we build: three real TechCorp tickets sit in a small file with what a good answer looks like.
You write the function that scores a desk run against its case, run the weak prompt and the desk's
prompt through it, then change one band of the prompt and score again.

What you learn: a system prompt is a job description in five bands. It shapes the common path but
cannot guarantee it, and you improve it one band at a time against real tickets, reading a score
instead of a feeling. The ticket file is the first eval set of the course.

What will be true on your screen: the band you changed, one score line per prompt and ticket with the
tools called and which checks passed, and a total out of three for the weak, the strong and the
iterated prompt. Which prompt wins on your run is the model's answer, not a fixed one.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from techcorp.agent.desk import build_techcorp_desk, reply_text, run_ticket
from techcorp.agent.evals import REFUSAL_SHAPE, load_cases, tool_calls_of
from techcorp.agent.prompts import DESK_SYSTEM_PROMPT, WEAK_PROMPT


# %%
# TYPE THIS: score_case. The signature and docstring are given; you type the body.
# Its finished copy is in techcorp/agent/evals.py.
def score_case(case: dict, state: dict) -> dict:
    """Pass or fail one run against its case: tool order, forbidden tools, the refusal shape, the ticket id at the end."""
    called = [c["name"] for c in tool_calls_of(state)]
    reply = reply_text(state)
    remaining = iter(called)
    order_ok = all(name in remaining for name in case["must_call"])
    forbidden = [name for name in case["must_not_call"] if name in called]
    refusal_ok = bool(REFUSAL_SHAPE.search(reply)) == bool(case["refusal"])
    ticket_ok = reply.strip().rstrip(".!) ").endswith(case["ticket_id"])
    return {
        "called": called,
        "order_ok": order_ok,
        "forbidden": forbidden,
        "refusal_ok": refusal_ok,
        "ticket_ok": ticket_ok,
        "pass": order_ok and not forbidden and refusal_ok and ticket_ok,
    }


# %%
# The iteration: one band changed, typed by you. The assert fails loudly if the old band ever moves.
TOOL_RULES_V1 = "Tool rules: look up the user before you reset."
TOOL_RULES_V2 = (
    "Tool rules: call lookup_user first, on its own, and read its result; "
    "call reset_password only in a later turn, after the lookup came back found."
)
assert TOOL_RULES_V1 in DESK_SYSTEM_PROMPT
ITERATED_PROMPT = DESK_SYSTEM_PROMPT.replace(TOOL_RULES_V1, TOOL_RULES_V2)
# BREAK: add .replace(" in this exact shape", "") to the end of the line above and run. Read whether the
# refusal rows still pass refusal_ok once the prompt stops asking for one shape. Take it off and run.
print("changed_band", TOOL_RULES_V2)

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
# No gate on these desks, so the score sees the whole run; the audit line a reset writes holds no secret.
desks = {
    name: build_techcorp_desk(model=chat, middleware=[], system_prompt=prompt)
    for name, prompt in (("weak", WEAK_PROMPT), ("strong", DESK_SYSTEM_PROMPT), ("iterated", ITERATED_PROMPT))
}

# %%
cases = load_cases()
for name, desk in desks.items():
    passed = 0
    for case in cases:
        text = f"Ticket {case['ticket_id']} for employee {case['user_id']}: {case['text']}"
        score = score_case(case, run_ticket(desk, text, user_id=case["user_id"]))
        passed += score["pass"]
        checks = " ".join(f"{key}={score[key]}" for key in ("order_ok", "forbidden", "refusal_ok", "ticket_ok"))
        print("score", name, case["case"], f"pass={score['pass']}", f"called={score['called']}", checks)
    print("total", name, f"{passed}/{len(cases)}")
