# %% [markdown]
# bind_tools and read the tool call the model proposed.
#
# When this works, the proposed call is on screen, the tool is run by
# hand, the ToolMessage uses the matching tool_call_id, and the model
# answers. The break appends a ToolMessage with a wrong id.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

import config
from techcorp.tools.accounts import (
    dummy_runtime,
    grant_access,
    lookup_user,
    reset_password,
)

tickets_path = root / "techcorp" / "data" / "tickets.jsonl"
ticket = None
for line in tickets_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if row["ticket_id"] == "TC-1001":
        ticket = row
        break

print("model", config.CHAT_MODEL)
print("ticket_id", ticket["ticket_id"])
print("text", ticket["text"])

tools = [lookup_user, reset_password, grant_access]
tool_by_name = {item.name: item for item in tools}

model = config.get_chat_model()
bound = model.bind_tools(tools)
system = SystemMessage(
    content=(
        "You are the TechCorp IT desk. Use tools. "
        "Look up the user before you reset. Never reset without a user id."
    )
)
human = HumanMessage(
    content=(
        f"Ticket {ticket['ticket_id']} for employee {ticket['customer_id']}: "
        f"{ticket['text']}"
    )
)

# %%
ai = bound.invoke([system, human])
print("ai_type", type(ai).__name__)
print("ai_content", ai.content)
print("tool_calls", ai.tool_calls)
if ai.tool_calls:
    call = ai.tool_calls[0]
    print("proposed_name", call.get("name"))
    print("proposed_args", call.get("args"))
    print("proposed_id", call.get("id"))
    name = call.get("name")
    args = dict(call.get("args") or {})
    tool_call_id = call.get("id")
    if name == "reset_password":
        result = reset_password.func(
            str(args.get("user_id") or ticket["customer_id"]),
            runtime=dummy_runtime(),
        )
    else:
        result = tool_by_name[name].invoke(args)
    print("hand_result", result)
    matching = ToolMessage(
        content=json.dumps(result, ensure_ascii=True),
        tool_call_id=tool_call_id,
        name=name,
    )
    final = bound.invoke([system, human, ai, matching])
    print("final_type", type(final).__name__)
    print("final_content", final.content)
    print("final_tool_calls", final.tool_calls)
else:
    print("no tool_calls; the model answered in words")
    matching = None
    tool_call_id = None
    name = None

# %%
print("BREAK: ToolMessage with a wrong tool_call_id")
try:
    if matching is None:
        print("skip_wrong_id", "no proposed tool call to mismatch")
    else:
        wrong = ToolMessage(
            content=matching.content,
            tool_call_id="not-the-real-id",
            name=name,
        )
        broken = bound.invoke([system, human, ai, wrong])
        print("wrong_id_type", type(broken).__name__)
        print("wrong_id_content", broken.content)
        print("wrong_id_tool_calls", broken.tool_calls)
except Exception as err:
    print("wrong_id_error_type", type(err).__name__)
    print("wrong_id_error", err)
