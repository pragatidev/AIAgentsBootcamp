# %% [markdown]
# create_deep_agent for a research task.
#
# Virtual filesystem. Stream node and tool names. Print the todo key,
# the virtual files, the first 40 lines of the report if it exists,
# and the message count. If the agent never wrote todos or a report,
# print that plainly.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from research_agent.agent import (
    build_research_agent,
    files_from_state,
    report_from_state,
)

QUESTION = (
    "What are the main reasons customers ask for returns or refunds, "
    "and which policy lines apply? Write a short report with sources."
)
RECURSION_LIMIT = 40

print("model", config.CHAT_MODEL)
print("backend", "StateBackend")
print("question", QUESTION)
print("recursion_limit", RECURSION_LIMIT)

agent = build_research_agent()
payload = {"messages": [{"role": "user", "content": QUESTION}]}
run_config = {
    "configurable": {"thread_id": "lab-17-2"},
    "recursion_limit": RECURSION_LIMIT,
}


def unpack_stream_item(item):
    if isinstance(item, tuple):
        if len(item) == 2:
            return item[0], item[1]
        if len(item) == 3:
            return item[1], item[2]
    return "updates", item


def print_tool_names(update) -> None:
    if not isinstance(update, dict):
        return
    messages = update.get("messages")
    if not isinstance(messages, list):
        return
    for message in messages:
        tool_calls = getattr(message, "tool_calls", None) or []
        for call in tool_calls:
            if isinstance(call, dict):
                name = call.get("name")
            else:
                name = getattr(call, "name", None)
            if name:
                print("tool", name)


print("cell", 1)
final_state = None
event_i = 0
try:
    for item in agent.stream(
        payload,
        run_config,
        stream_mode=["updates", "values"],
    ):
        mode, data = unpack_stream_item(item)
        if mode == "values" and isinstance(data, dict):
            final_state = data
            continue
        if mode != "updates" or not isinstance(data, dict):
            event_i += 1
            print("event", event_i, type(data).__name__)
            continue
        for node, update in data.items():
            event_i += 1
            print("event", event_i, node)
            print_tool_names(update)
except Exception as exc:
    print("run_error", type(exc).__name__)
    print(str(exc))

print("cell", 2)
print("event_count", event_i)
if not isinstance(final_state, dict):
    print("final_state", "none")
else:
    print("todo_key", "todos")
    todos = final_state.get("todos")
    if not todos:
        print("The agent never wrote todos.")
        print("todos", todos)
    else:
        print("todos", todos)
    files = files_from_state(final_state)
    print("virtual_files", sorted(str(k) for k in files.keys()))
    report_path, report_text = report_from_state(final_state)
    if not report_text:
        print("The agent never wrote a report.")
    else:
        print("report_path", report_path)
        lines = report_text.splitlines()
        print("report_first_40")
        for line in lines[:40]:
            print(line)
        print("report_line_count", len(lines))
    messages = final_state.get("messages") or []
    print("message_count", len(messages))
    tokens = 0
    model_calls = 0
    for message in messages:
        kind = getattr(message, "type", "")
        if kind == "ai":
            model_calls += 1
        usage = getattr(message, "usage_metadata", None) or {}
        if isinstance(usage, dict):
            tokens += int(usage.get("total_tokens") or 0)
        else:
            tokens += int(getattr(usage, "total_tokens", 0) or 0)
    print("ai_message_count", model_calls)
    print("token_count", tokens if tokens else "unknown")
