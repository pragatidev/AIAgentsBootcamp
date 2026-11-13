# %%
"""Lab 29.6: a poisoned tool description, caught.

What we build: a tripwire at bind time. A third-party weather server (dataflow/mcp/fixtures/
weather_server.py) offers two tools whose descriptions carry instructions aimed at the model. First you
see exactly what the desk hands the model, then a model that follows the instruction issues a refund
nobody asked for. You type screen_tool, which reads every description before the desk binds it, and the
desk refuses the tools that trip it.

What you learn: a tool's description is text the model reads as instructions on every turn, and the user
never sees it. A server's annotations are claims too: both weather tools say they are read-only. A screen
catches the poisons people have already written: markup that hides text, phrases that ask for silence,
a mention of another tool, a URL, a very long description. It is a tripwire, not a guarantee; the controls
that hold are the allowlist (29.7), the scopes (29.4) and the person in front of anything destructive (29.8).

What will be true on your screen: the versions; each weather tool's description exactly as the model
receives it, with the read-only claim in its metadata; a stand-in model that obeys calling get_weather,
then refund, and replying about the weather only, with one ledger row written; then each tool's screen
result, the desk binding only the clean ones, and no poison left in what the model receives.
"""

from pathlib import Path
from importlib.metadata import version
import json
import os
import sys
import tempfile

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import re

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from dataflow.mcp.bind import bind_mcp_tools, build_desk, close_mcp
from dataflow.mcp.fixtures.weather_server import weather
from dataflow.mcp.kb_server import kb
from dataflow.mcp.screen import CONCEALMENT, MARKUP, MAX_LENGTH, URL
from dataflow.mcp.server import mcp as orders
from dataflow.rag.desk import ask_desk, reply_text
from dataflow.tools.refund import read_refunds

print("mcp", version("mcp"), "fastmcp", version("fastmcp"), "langchain", version("langchain"))

# The refund writes a ledger row. A temp ledger keeps the real one clean.
ledger = tempfile.NamedTemporaryFile(prefix="refunds-", suffix=".jsonl", delete=False)
ledger.close()
os.environ["DATAFLOW_REFUNDS_PATH"] = ledger.name


# %%
# What the desk hands the model from a server it did not write.
weather_tools = bind_mcp_tools(weather)
for tool in weather_tools:
    print("tool", tool.name)
    print("  description_the_model_receives", json.dumps(convert_to_openai_tool(tool)["function"]["description"]))
    print("  metadata_mcp", json.dumps(tool.metadata["mcp"]))


# %%
# A stand-in model that does what the description says, the way a real model sometimes does.
class Obeys(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


def tools_ran(state: dict) -> list:
    return [(c["name"], c["args"]) for m in state["messages"] for c in (getattr(m, "tool_calls", None) or [])]


orders_tools = bind_mcp_tools(orders)
kb_tools = bind_mcp_tools(kb)
obeys = Obeys(responses=[
    call("get_weather", {"city": "Pune"}, "w1"),
    call("refund", {"order_id": "DF-1001", "amount": 999, "reason": "weather"}, "r1"),
    AIMessage(content="It is sunny in Pune, 21 degrees."),
])
before = len(read_refunds())
state = ask_desk(build_desk(model=obeys, tools=orders_tools + weather_tools), "What is the weather in Pune?")
print("unscreened tools_ran", tools_ran(state))
print("unscreened reply", reply_text(state))
print("unscreened ledger_rows_added", len(read_refunds()) - before)


# %%
# TYPE THIS: screen_tool. The signature and docstring are given; you type the body.
# Its finished copy is screen_tool in dataflow/mcp/screen.py, where MARKUP, CONCEALMENT, URL and MAX_LENGTH live.
def screen_tool(tool, known_tool_names: list[str]) -> list[str]:
    """The reasons tool's description looks like instructions to the model. Empty means it passed."""
    text = str(getattr(tool, "description", "") or "")
    lowered = text.lower()
    reasons = []
    if MARKUP.search(text):
        reasons.append("markup that can hide text")
    for phrase in CONCEALMENT:
        if phrase in lowered:
            reasons.append(f"asks to keep something from the user: {phrase!r}")
    for name in known_tool_names:
        if name != tool.name and re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
            reasons.append(f"names another tool: {name}")
    if URL.search(text):
        reasons.append("contains a URL")
    if len(text) > MAX_LENGTH:
        reasons.append(f"longer than {MAX_LENGTH} characters")
    return reasons


# BREAK: delete the three lines of the "names another tool" check above (the for loop and its body) and
# run. get_weather is still refused for its markup and its request for silence, but get_forecast, the
# rewritten poison with no markup that only names refund, passes and is bound. Put the lines back and run.


# %%
every_tool = orders_tools + kb_tools + weather_tools
names = [tool.name for tool in every_tool]
bound = []
for tool in every_tool:
    reasons = screen_tool(tool, names)
    print("screen", tool.metadata["mcp"]["server"]["name"], tool.name, reasons or "clean")
    if not reasons:
        bound.append(tool)
print("desk_binds", [tool.name for tool in bound])
received = [convert_to_openai_tool(tool)["function"]["description"] for tool in bound]
print("poison_reaches_model", any("DF-1001" in text and "999" in text for text in received))
close_mcp()
