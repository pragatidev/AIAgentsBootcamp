# %% [markdown]
# Read a coding-agent harness on this repo.
#
# When this works, AGENTS.md prints its sections, the tools and
# permission lines are listed, the model from config.py adds a line to
# notes.md, a planted shell with no permission line still runs, and the
# committed table returns a typed miss.

# %%
from pathlib import Path
import difflib
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langchain_core.messages import HumanMessage

import config
from techcorp.harness.coding_agent import (
    AGENTS_PATH,
    PERMISSIONS,
    build_coding_desk,
    load_agents_md,
    make_tools,
    planted_shell_table,
)

notes_path = root / "techcorp" / "harness" / "sandbox" / "notes.md"
committed_notes = notes_path.read_text(encoding="utf-8")
print("model", config.CHAT_MODEL)
print("agents_path", AGENTS_PATH.as_posix())

# %%
print("cell", "agents_md")
text = load_agents_md()
print(text)
for heading in (
    "## Role",
    "## Scope",
    "## Tool rules",
    "## Permissions",
    "## Refusal",
    "## Sandbox",
):
    print("heading", heading, heading in text)
print("tools", ["read_file", "write_file", "run_tests", "shell"])
print("permission_lines", PERMISSIONS)

# %%
print("cell", "allowed_edit")
before = notes_path.read_text(encoding="utf-8")
print("notes_before")
print(before)
desk = build_coding_desk()
task = (
    "Call write_file. path=techcorp/harness/sandbox/notes.md. "
    "content is the current file plus one new line that says: "
    "checked by the agent. Do not change anything else."
)
print("task", task)
out = desk.invoke({"messages": [HumanMessage(content=task)]})
messages = out.get("messages") or []
print("message_count", len(messages))
for msg in messages:
    kind = getattr(msg, "type", type(msg).__name__)
    calls = getattr(msg, "tool_calls", None) or []
    if calls:
        print("tool_calls", calls)
    content = getattr(msg, "content", "") or ""
    if content:
        print("content", str(content)[:500])
after = notes_path.read_text(encoding="utf-8")
diff = "".join(
    difflib.unified_diff(
        before.splitlines(True),
        after.splitlines(True),
        fromfile="notes.md",
        tofile="notes.md",
    )
)
print("diff")
print(diff if diff else "(notes.md unchanged)")
print("checked_line", "checked by the agent" in after)

# %%
print("cell", "break")
planted = make_tools(planted_shell_table(), fall_through=True)
shell = next(item for item in planted if item.name == "shell")
reached = shell.invoke({"command": "echo shell reached"})
print("planted_shell", reached)
print("stdout", (reached.get("stdout") or "").strip())

print("cell", "fix")
fixed = make_tools(PERMISSIONS, fall_through=False)
denied = next(item for item in fixed if item.name == "shell")
miss = denied.invoke({"command": "echo shell reached"})
print("denied_miss", miss)
print("denied", miss.get("denied"))
print("reason", miss.get("reason"))

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
notes_path.write_text(committed_notes, encoding="utf-8")
print("restored_notes", notes_path.read_text(encoding="utf-8") == committed_notes)
