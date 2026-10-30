# %%
"""Lab 4.15: summarization and tool-call-limit middleware.

What we build: two guards on the desk, each one entry in the middleware list. You type a summarizer
that folds old turns into a short summary in a shape you choose, and watch a six-turn thread stay
small. Then a limit on tool calls stops a ticket that asks for more lookups than you allowed, and you
fix it by counting what the ticket needs.

What you learn: middleware that keeps the transcript from growing forever, and middleware that turns a
runaway into a stop with a reason instead of a bill. And the catch you see yourself: a summary is a
model's writing. It keeps what its prompt asks for, and it can invent what its prompt asks for too.

What will be true on your screen: per turn, how many messages the thread holds, whether a summary is in
it, and how many summaries have been written; the newest summary in your four slots; then the lookup
ticket with the limit, each lookup's result or the limit's refusal, and the reply. This desk can only
look people up, so no turn can write anything.
"""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.agents.middleware import SummarizationMiddleware, ToolCallLimitMiddleware
from langgraph.checkpoint.memory import InMemorySaver

import config
from techcorp.agent.desk import build_techcorp_desk, reply_text, run_ticket
from techcorp.tools.accounts import lookup_user

# %%
# TYPE THIS: SUMMARY_PROMPT and desk_summarizer. The names and the docstring are given; you type the rest.
# The finished copies are SUMMARY_PROMPT in techcorp/agent/prompts.py and desk_summarizer in desk.py.
SUMMARY_PROMPT = """Summarize this TechCorp IT desk conversation in exactly four slots.

Employee id: the employee's id, as written in the messages.
Ticket id: the ticket id, as written in the messages.
Done: each tool that ran and its outcome. Never copy a password, a temporary password or any other secret.
Still open: what the employee still needs.

Write None for an empty slot. Never write a value that is not in the messages.

Messages:
{messages}
"""


def desk_summarizer(model) -> SummarizationMiddleware:
    """Fold old turns into the desk's four-slot summary once the thread passes the trigger, keeping the newest turns."""
    return SummarizationMiddleware(model, trigger=("messages", 4), keep=("messages", 2), summary_prompt=SUMMARY_PROMPT)


# BREAK: delete summary_prompt=SUMMARY_PROMPT from desk_summarizer and run. The library's default
# prompt writes the summary instead; read what it kept and what it added. Put it back and run.

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))

# %%
desk = build_techcorp_desk(model=chat, tools=[lookup_user], middleware=[desk_summarizer(chat)], checkpointer=InMemorySaver())
TURNS = [
    "Ticket TC-1101: Hi, I am employee E-4101. Please look me up.",
    "Which department am I in?",
    "Which groups am I in?",
    "Is VPN enabled on my account?",
    "What email address do you have for me?",
    "Thanks. Give me a one line recap of what you found, ending with the ticket id.",
]


def summaries_in(state: dict) -> list:
    # The summary arrives as a human message the library marks with lc_source "summarization".
    return [m for m in state["messages"] if m.additional_kwargs.get("lc_source") == "summarization"]


written: list[str] = []
for n, text in enumerate(TURNS, 1):
    state = run_ticket(desk, text, user_id="E-4101", thread_id="lab-4-15-summary")
    for summary in summaries_in(state):
        if summary.text not in written:
            written.append(summary.text)
    print("turn", n, "held", len(state["messages"]), "summary_in_state", bool(summaries_in(state)), "summaries_written", len(written))
print("reply", reply_text(state).strip())
print("summary_type", summaries_in(state)[-1].type if summaries_in(state) else None)
print("summary", written[-1] if written else None)

# %%
# The limit counts tool calls in one run. Count what a ticket needs and add one: three lookups need 4.
LOOKUP_LIMIT = 4
# BREAK: set LOOKUP_LIMIT = 2 and run. The third lookup is refused with the limit's message. Set it back.
limiter = ToolCallLimitMiddleware(run_limit=LOOKUP_LIMIT)
print("run_limit", limiter.run_limit, "exit_behavior", limiter.exit_behavior)
limit_desk = build_techcorp_desk(model=chat, tools=[lookup_user], middleware=[limiter])
state = run_ticket(limit_desk, "Ticket TC-1102: look up E-4101, E-4102 and E-4103 and tell me their departments.", user_id="E-4101")
for message in state["messages"]:
    if message.type == "tool":
        print("tool", message.status, message.content)
print("lookups_answered", sum(1 for m in state["messages"] if m.type == "tool" and m.status != "error"))
print("reply", reply_text(state).strip())
