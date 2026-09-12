# %% [markdown]
# Give it a filesystem and a todo list.
#
# Same research question, real folder backend under research_agent/reports/.
# Stream the todos key on every update and print each change. Then list
# the real files on disk.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from research_agent.agent import (
    PACKAGE_DIR,
    REPORTS_DIR,
    build_research_agent,
    find_report_files,
    make_real_backend,
)

QUESTION = (
    "What are the main reasons customers ask for returns or refunds, "
    "and which policy lines apply? Write a short report with sources."
)
RECURSION_LIMIT = 40

backend = make_real_backend()
print("model", config.CHAT_MODEL)
print("backend", type(backend).__name__)
print("backend_root", PACKAGE_DIR.as_posix())
print("reports_dir", REPORTS_DIR.as_posix())
print("question", QUESTION)
print("recursion_limit", RECURSION_LIMIT)

agent = build_research_agent(backend=backend)
payload = {"messages": [{"role": "user", "content": QUESTION}]}
run_config = {
    "configurable": {"thread_id": "lab-17-3"},
    "recursion_limit": RECURSION_LIMIT,
}


def unpack_stream_item(item):
    if isinstance(item, tuple):
        if len(item) == 2:
            return item[0], item[1]
        if len(item) == 3:
            return item[1], item[2]
    return "updates", item


print("cell", 1)
print("todo_key", "todos")
prev = None
todo_changes = 0
event_i = 0
final_state = None
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
            continue
        for node, update in data.items():
            event_i += 1
            print("event", event_i, node)
            if not isinstance(update, dict):
                continue
            if "todos" not in update:
                continue
            current = update.get("todos")
            if current == prev:
                continue
            todo_changes += 1
            print("todo_change", todo_changes, "node", node)
            print("todos", current)
            prev = current
except Exception as exc:
    print("run_error", type(exc).__name__)
    print(str(exc))

print("cell", 2)
print("todo_change_count", todo_changes)
if todo_changes == 0:
    print("The agent never wrote todos.")
    if isinstance(final_state, dict):
        print("todos", final_state.get("todos"))

print("disk_root", REPORTS_DIR.as_posix())
if REPORTS_DIR.is_dir():
    disk_files = []
    for path in sorted(REPORTS_DIR.rglob("*")):
        if path.is_file():
            disk_files.append(path.relative_to(PACKAGE_DIR).as_posix())
            print("disk_file", path.relative_to(PACKAGE_DIR).as_posix())
    if not disk_files:
        print("disk_files", "none")
else:
    print("disk_files", "none")

reports = find_report_files(PACKAGE_DIR)
if not reports:
    print("The agent never wrote a report.")
else:
    newest = max(reports, key=lambda p: p.stat().st_mtime)
    print("report_path", newest.as_posix())
    text = newest.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    print("report_first_40")
    for line in lines[:40]:
        print(line)

if isinstance(final_state, dict):
    messages = final_state.get("messages") or []
    print("message_count", len(messages))
    ai_count = sum(1 for m in messages if getattr(m, "type", "") == "ai")
    print("ai_message_count", ai_count)
