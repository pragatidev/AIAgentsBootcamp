# %% [markdown]
# Raw tool calling with no framework.
#
# The OpenAI SDK against Ollama with a tools list for reset_password.
# Print the raw tool_calls entry verbatim, parse it, run a tiny local
# function, append the tool message with the same id, call again, print
# the final sentence. Print the reasoning field once. Then a planted
# blank description, and whether the model called that tool.

# %%
from __future__ import annotations

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from openai import OpenAI

import config
from src.part1 import parse_tool_call_entry


def reset_password(user_id: str) -> str:
    return json.dumps(
        {
            "ok": True,
            "user_id": user_id,
            "action": "password_reset",
            "temp_password": "Tmp-" + user_id[-4:],
        }
    )


def raw_client() -> OpenAI:
    base = config.OLLAMA_BASE_URL.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    return OpenAI(base_url=base, api_key="ollama")


# %%
client = raw_client()
payload = {
    "model": config.CHAT_MODEL,
    "messages": [
        {"role": "user", "content": "Reset the password for user E-4101."}
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "reset_password",
                "description": "Reset a TechCorp employee laptop password.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "Employee id such as E-4101",
                        }
                    },
                    "required": ["user_id"],
                },
            },
        }
    ],
    "temperature": 0,
}
resp = client.chat.completions.create(**payload)
choice = resp.choices[0]
msg = choice.message
dump = msg.model_dump()
print("content", repr(msg.content))
print("finish_reason", choice.finish_reason)
print("usage", resp.usage.model_dump() if resp.usage else None)
reasoning = dump.get("reasoning") or dump.get("reasoning_content")
if reasoning is None:
    extra = getattr(msg, "model_extra", None) or {}
    if isinstance(extra, dict):
        reasoning = extra.get("reasoning") or extra.get("reasoning_content")
print("reasoning", reasoning)
print(
    "reasoning_is",
    "the model's hidden thinking before it answers; the tool call is in tool_calls, not here",
)
print("tool_calls", msg.tool_calls)
if not msg.tool_calls:
    raise SystemExit("model did not return tool_calls")
raw_entry = msg.tool_calls[0].model_dump()
print("raw_tool_calls_entry", json.dumps(raw_entry, ensure_ascii=True))
parsed = parse_tool_call_entry(msg.tool_calls[0])
print("parsed_name", parsed["name"])
print("parsed_id", parsed["id"])
print("parsed_arguments_json", parsed["arguments_json"])

# %%
result = reset_password(str(parsed["arguments"].get("user_id") or ""))
print("tool_result", result)
follow = {
    "model": config.CHAT_MODEL,
    "messages": [
        payload["messages"][0],
        {
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [raw_entry],
        },
        {
            "role": "tool",
            "tool_call_id": parsed["id"],
            "content": result,
        },
    ],
    "tools": payload["tools"],
    "temperature": 0,
}
final = client.chat.completions.create(**follow)
final_msg = final.choices[0].message
print("final_sentence", final_msg.content)
print("final_finish", final.choices[0].finish_reason)

# %%
# Planted: a tool whose description is blank.
blank_payload = {
    "model": config.CHAT_MODEL,
    "messages": [
        {"role": "user", "content": "Wipe the disk for user E-4101."}
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "wipe_disk",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"}
                    },
                    "required": ["user_id"],
                },
            },
        }
    ],
    "temperature": 0,
}
blank_resp = client.chat.completions.create(**blank_payload)
blank_msg = blank_resp.choices[0].message
blank_names = []
if blank_msg.tool_calls:
    for item in blank_msg.tool_calls:
        blank_names.append(parse_tool_call_entry(item)["name"])
print("blank_description_tool", "wipe_disk")
print("blank_tool_called", "wipe_disk" in blank_names)
print("blank_tool_names", blank_names)
print("blank_content", repr(blank_msg.content))
print("blank_finish", blank_resp.choices[0].finish_reason)
