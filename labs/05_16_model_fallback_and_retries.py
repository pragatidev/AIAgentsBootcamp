# %%
"""Lab 4.16: model fallback and retries.

What we build: we make the desk keep answering when the world fails it. You type a two-piece guard:
retry the same model when a failure might not repeat, and switch to a model you trust when it will.
Then a flaky directory gets the same treatment at the tool.

What you learn: the built-in middlewares for failure, and the rule from lecture 4.7 in practice: a
fault the world causes is retried or handled, a miss the tool returns is an answer and never retried.
Plus the one setting that decides whether retry and fallback work together at all.

What will be true on your screen: the real 404 from a model that does not exist; the fallback list with
one model in it; which model answered each run and how long it took; a planted fault counted as one
retry; the flaky lookup retried once and answered; and the unknown employee answered as a typed miss
with no retry at all.
"""

from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.agents.middleware import (
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.tools import StructuredTool

import config
from techcorp.agent.desk import build_techcorp_desk, reply_text, run_ticket
from techcorp.tools.accounts import lookup_user

good = config.get_chat_model()
print("model", type(good).__name__, getattr(good, "model", None) or getattr(good, "model_name", None))


# %%
# TYPE THIS: is_transient and resilience. The signatures and docstrings are given; you type the bodies.
# The finished copies are in techcorp/agent/resilience.py.
def is_transient(exc) -> bool:
    """True when the same call might pass if tried again; False for a status that will fail the same way."""
    return getattr(exc, "status_code", None) not in {400, 401, 403, 404}


def resilience(fallback_model) -> list:
    """Retry the same model on a transient fault, then fall back to a model you trust. The fallback is the outer layer."""
    return [
        ModelFallbackMiddleware(fallback_model),
        ModelRetryMiddleware(max_retries=2, retry_on=is_transient, on_failure="error", initial_delay=0.1, backoff_factor=0.0, jitter=False),
    ]


# BREAK: delete on_failure="error" from the retry above and run. The dead-port run's reply becomes
# "Model call failed after 3 attempts with ...", and the fallback never runs, because nothing raised.
# Put on_failure="error" back and run.


def label(model) -> str:
    return str(getattr(model, "model", None) or getattr(model, "model_name", None))


def run(desk, text: str, user_id: str) -> dict:
    started = time.perf_counter()
    state = run_ticket(desk, text, user_id=user_id)
    last = state["messages"][-1]
    print("answered_by", last.response_metadata.get("model") or last.response_metadata.get("model_name"))
    print("seconds", round(time.perf_counter() - started, 2))
    print("reply", reply_text(state).strip())
    return state


VPN = "Ticket TC-1002 for employee E-4102: VPN connects then drops every few minutes from the home office."

# %%
# A model id the local server does not have: a real 404, called directly first.
bad = config.get_local_chat_model(model="qwen3-does-not-exist-lab")
try:
    bad.invoke("ping")
except Exception as exc:
    print("bad_model_error", type(exc).__name__, "status_code", getattr(exc, "status_code", None), "transient", is_transient(exc))
stack = resilience(good)
print("fallback_models", [label(m) for m in stack[0].models])
run(build_techcorp_desk(model=bad, tools=[lookup_user], middleware=stack), VPN, "E-4102")

# %%
# A model server that is not there: no status code, so the retry tries twice more, then the fallback answers.
dead = config.get_local_chat_model(base_url="http://127.0.0.1:1")
run(build_techcorp_desk(model=dead, tools=[lookup_user], middleware=resilience(good)), VPN, "E-4102")


# %%
# PLANTED: a model wrapper that raises on its first call and then passes every call through.
class FailOnceThenCall:
    def __init__(self, inner, events: list) -> None:
        self.inner, self.events = inner, events

    def bind_tools(self, tools, **kwargs):
        return FailOnceThenCall(self.inner.bind_tools(tools, **kwargs), self.events)

    def bind(self, **kwargs):
        return FailOnceThenCall(self.inner.bind(**kwargs), self.events)

    def invoke(self, messages, **kwargs):
        if "raise" not in self.events:
            self.events.append("raise")
            raise ConnectionError("planted: the first model call fails")
        self.events.append("ok")
        return self.inner.invoke(messages, **kwargs)


events: list = []
desk = build_techcorp_desk(model=FailOnceThenCall(good, events), tools=[lookup_user], middleware=resilience(good))
run(desk, "Ticket TC-1006 for employee E-4106: please look me up and tell me which department and groups I am in.", "E-4106")
print("model_calls", len(events), "faults_raised", events.count("raise"))
# A retry is a fault followed by another call to the same model.
print("retries", events[:-1].count("raise"))

# %%
# PLANTED: a directory that is down for one call while a fault is armed. ToolError is the outer layer,
# ToolRetry the inner, with on_failure="error" so a fault that outlasts the retries reaches the error handler.
tool_events: list = []
armed = {"faults": 0}


def flaky_lookup_fn(query: str) -> dict:
    if armed["faults"]:
        armed["faults"] -= 1
        tool_events.append("raise")
        raise ConnectionError("directory service unreachable")
    tool_events.append("ok")
    return lookup_user.invoke({"query": query})


flaky_lookup = StructuredTool.from_function(flaky_lookup_fn, name="lookup_user", description=lookup_user.description)


def directory_down(exc, request) -> str:
    # Name the kind of failure, never the raw error text, which can carry internal detail.
    return f"The directory did not answer ({type(exc).__name__}). Try again in a few minutes."


tool_guard = [
    ToolErrorMiddleware(on_error=directory_down, tools=["lookup_user"]),
    ToolRetryMiddleware(tools=["lookup_user"], max_retries=2, on_failure="error", initial_delay=0.1, backoff_factor=0.0, jitter=False),
]
tool_desk = build_techcorp_desk(model=good, tools=[flaky_lookup], middleware=tool_guard)
for user_id, faults in (("E-4106", 1), ("E-9999", 0)):
    armed["faults"] = faults
    before = len(tool_events)
    state = run(tool_desk, f"Ticket TC-1006 for employee {user_id}: please look me up and tell me which department and groups I am in.", user_id)
    calls = tool_events[before:]
    print("lookup", user_id, "tool_calls", len(calls), "tool_faults", calls.count("raise"))
    for message in state["messages"]:
        if message.type == "tool":
            print("tool", message.status, message.content)
