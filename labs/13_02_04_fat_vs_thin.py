# %% [markdown]
# Fat SKILL.md versus thin, on tokens.
#
# When this works, both token counts print, the fat body carries the
# policy line, the thin body without L3 misses it, and loading the
# reference brings the line back. The fat file never hits disk.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langchain_core.messages import HumanMessage

import config
from dataflow.graphs.rag_tool_cycle import build_rag_tool_cycle
from dataflow.skills.loader import (
    TOKEN_METHOD,
    count_tokens,
    load_body,
    load_reference,
    load_skills,
)
from dataflow.tools.orders import lookup_order

ASK = "Please refund order DF-1001, the lamp is unused"


def cites_window(reply: str) -> bool:
    """The reference's window number, however the model phrases it.

    The reference says 30 days from delivery and 30 days of delivery, and a
    model that read it may say 30-day. A reply with no 30 in it never read
    the line.
    """
    return "30 days" in reply or "30-day" in reply


def last_reply(messages) -> str:
    for message in reversed(list(messages or [])):
        if list(getattr(message, "tool_calls", None) or []):
            continue
        text = str(getattr(message, "content", "") or "")
        if text:
            return text
    return ""


def run_desk(system: str, model) -> str:
    graph = build_rag_tool_cycle(
        model=model,
        tools=[lookup_order],
        system=system,
    )
    out = graph.invoke({"messages": [HumanMessage(content=ASK)]})
    return last_reply(out.get("messages"))


print("model", config.CHAT_MODEL)
print("token_method", TOKEN_METHOD)
skills = load_skills()
thin_body = load_body(skills[0])
policy = load_reference(skills[0], "policy_lines.md")
fat = thin_body + "\n\n" + policy
print("fat_tokens", count_tokens(fat))
print("thin_tokens", count_tokens(thin_body))
model = config.get_chat_model()
print("cell", "fat")
fat_reply = run_desk(
    "You are the DataFlow desk.\n" + fat,
    model,
)
print("fat_reply", fat_reply)
print("fat_cites_line", cites_window(fat_reply))

print("cell", "thin")
thin_reply = run_desk(
    "You are the DataFlow desk.\n" + thin_body,
    model,
)
print("thin_reply", thin_reply)

# %%
print("cell", "break")
print("BREAK: thin path with L3 never loaded misses the policy line")
print("thin_without_l3", thin_reply)
print("thin_misses_line", not cites_window(thin_reply))

# %%
print("cell", "fix")
print("FIX: the body points at the reference, the lab loads it, the line comes back")
print("pointer", "references/policy_lines.md" in thin_body)
loaded = thin_body + "\n\n" + policy
print("thin_plus_l3_tokens", count_tokens(loaded))
fixed_reply = run_desk(
    "You are the DataFlow desk.\n" + loaded,
    model,
)
print("thin_plus_l3_reply", fixed_reply)
print("line_comes_back", cites_window(fixed_reply))
