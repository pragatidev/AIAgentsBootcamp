# %% [markdown]
# Summarization and tool-call-limit middleware.
#
# When this works, a 6-turn thread is summarised and a ticket that
# asks for three grants hits the tool call limit. Both fire on screen.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.agents.middleware import SummarizationMiddleware, ToolCallLimitMiddleware
from langgraph.checkpoint.memory import InMemorySaver

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk, run_ticket

print("model", config.CHAT_MODEL)


def content_text(msg) -> str:
    content = getattr(msg, "content", "") or ""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


# %%
saver = InMemorySaver()
summarizer = SummarizationMiddleware(
    config.get_chat_model(),
    trigger=("messages", 4),
    keep=("messages", 2),
)
sum_desk = build_techcorp_desk(
    middleware=[summarizer],
    checkpointer=saver,
)
thread = "lab-5-15-summary"
ctx = DeskContext(user_id="E-4101")
turns = [
    "Ticket TC-1001. I am Amina Cole. I cannot log in after the weekend.",
    "It is the laptop password. Can you help?",
    "Please look me up first.",
    "If you reset it, tell me when it expires.",
    "Also, is my VPN still enabled?",
    "Thanks. What is my department on file?",
]
before_count = None
after_state = None
for index, turn in enumerate(turns, start=1):
    out = sum_desk.invoke(
        {"messages": [{"role": "user", "content": turn}]},
        config={"configurable": {"thread_id": thread}},
        context=ctx,
    )
    count = len(out.get("messages") or [])
    print("turn", index, "message_count", count)
    if index == 2:
        before_count = count
        print("count_before_summary_window", before_count)
    after_state = out

print("count_after", len(after_state.get("messages") or []) if after_state else None)
print("count_before", before_count)
if after_state:
    for msg in after_state["messages"]:
        kind = getattr(msg, "type", type(msg).__name__)
        text = content_text(msg)
        lowered = text.lower()
        if "summary" in lowered or "session intent" in lowered:
            print("summary_type", kind)
            print("summary_message_text", text)

# %%
limiter = ToolCallLimitMiddleware(run_limit=2)
print("exit_behavior", limiter.exit_behavior)
limit_desk = build_techcorp_desk(middleware=[limiter])
grant_text = (
    "Ticket TC-1004 for employee E-4104: please grant me access to "
    "finance-q3, legal-share, and payroll-share. Do all three."
)
limited = run_ticket(
    limit_desk,
    grant_text,
    user_id="E-4104",
    thread_id="lab-5-15-limit",
)
print("limit_message_count", len(limited.get("messages") or []))
for index, msg in enumerate(limited.get("messages") or []):
    kind = getattr(msg, "type", type(msg).__name__)
    text = content_text(msg)
    print("hop", index, "type", kind)
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        print("tool_calls", tool_calls)
    print("content", text)
    print("---")
    if "limit" in text.lower():
        print("limit_text_verbatim", text)
print("exit_behavior_verbatim", limiter.exit_behavior)
