# %%
"""Lab 4.22: stream the TechCorp reply token by token.

What we build: we stream one TechCorp ticket through the desk and watch three things from the same
run: the reply typing itself out, the node that is working, and a small handler you write that adds up
every token the run used.

What you learn: streaming and callbacks are two doors on one run. Messages mode is for the screen,
updates mode says which step is running, and a callback handler sees every model call without the desk
changing, which is where token budgets and traces come from.

What will be true on your screen: an update line per node as it finishes (the model, the gate parking
the reset, then after the approval the tools and the model again), the reply typing out, the seconds to
its first word and in total, then your handler's tokens and calls beside the library's own counter.
"""

from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from langchain_core.callbacks import BaseCallbackHandler, UsageMetadataCallbackHandler
from langgraph.types import Command

import config
from techcorp.agent.context import DeskContext
from techcorp.agent.desk import build_techcorp_desk


# %%
# TYPE THIS: on_llm_end. The class, __init__ and docstring are given; you type the method.
# Its finished copy is TokenCounter in techcorp/agent/usage.py.
class TokenCounter(BaseCallbackHandler):
    """Adds up the tokens of every model call in a run. Pass it in config={"callbacks": [counter]}."""

    def __init__(self) -> None:
        super().__init__()
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.calls = 0

    def on_llm_end(self, response, **kwargs) -> None:
        self.calls += 1
        for generations in response.generations:
            for generation in generations:
                usage = generation.message.usage_metadata or {}
                self.input_tokens += usage.get("input_tokens", 0)
                self.output_tokens += usage.get("output_tokens", 0)
                self.total_tokens += usage.get("total_tokens", 0)


# BREAK: rename on_llm_end to on_chat_model_end and run. token_count and calls print 0, because
# LangChain has no on_chat_model_end callback: chat models end on on_llm_end too. Rename it back and run.

# %%
# reasoning=False: with thinking on, this ticket thought until the 4096-token cap; off, the reply itself streams.
chat = config.get_chat_model(reasoning=False)
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
desk = build_techcorp_desk(model=chat)
counter, builtin = TokenCounter(), UsageMetadataCallbackHandler()
run_config = {"configurable": {"thread_id": "lab-4-22"}, "callbacks": [counter, builtin]}
ctx = DeskContext(user_id="E-4101")
ticket = "Ticket TC-1001 for employee E-4101: I forgot my laptop password after the long weekend. Please reset it."

started = time.perf_counter()
first_word = None
typing = False


def stream(payload) -> bool:
    """Stream one leg of the run; print the reply as it types and one line per node update. True if it parked."""
    global first_word, typing
    parked = False
    for mode, data in desk.stream(payload, config=run_config, context=ctx, stream_mode=["messages", "updates"]):
        if mode == "messages":
            chunk, meta = data
            # Only the model node's words: a tool result never types itself onto the screen.
            if meta.get("langgraph_node") == "model" and chunk.text:
                if first_word is None:
                    first_word = time.perf_counter() - started
                if not typing:
                    print("reply ", end="")
                    typing = True
                print(chunk.text, end="")
        else:
            if typing:
                print()
                typing = False
            for node, update in data.items():
                if node == "__interrupt__":
                    parked = True
                    print("update __interrupt__ parked", update[0].value["action_requests"][0]["name"])
                    continue
                kinds = [m.type for m in (update or {}).get("messages", [])] if isinstance(update, dict) else []
                print("update", node, kinds)
    return parked


if stream({"messages": [{"role": "user", "content": ticket}]}):
    # The person approves the parked reset; the same handler keeps counting the resumed run.
    stream(Command(resume={"decisions": [{"type": "approve"}]}))

print("seconds_to_first_word", round(first_word, 2) if first_word is not None else None)
print("seconds_total", round(time.perf_counter() - started, 2))
print("token_count", counter.total_tokens, "input", counter.input_tokens, "output", counter.output_tokens, "calls", counter.calls)
print("builtin", builtin.usage_metadata)
