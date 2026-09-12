# %% [markdown]
# Model fallback and retries.
#
# When this works, a missing Ollama tag fails for real and the
# fallback model answers. Then a planted wrapper raises once and
# ModelRetryMiddleware retries it. The retry count is printed.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware
from langchain_ollama import ChatOllama

import config
from techcorp.agent.desk import build_techcorp_desk, run_ticket

print("model", config.CHAT_MODEL)
print("ollama_base", config.OLLAMA_BASE_URL)

bad = ChatOllama(
    model="qwen3-does-not-exist-lab",
    base_url=config.OLLAMA_BASE_URL.rstrip("/"),
    temperature=0,
)
good = config.get_chat_model()

print("BREAK is a missing model name, not a fake exception")
try:
    bad.invoke("ping")
    print("missing_model_unexpected_success")
except Exception as err:
    print("first_model_error_type", type(err).__name__)
    print("first_model_error", err)
    fallback_error_text = str(err)

# ModelFallbackMiddleware(first_model, *additional_models).
# The missing tag is the create_agent primary so the first call fails
# for real. first_model on the middleware is the first fallback after
# that miss; additional models follow. There is no additional_models=
# keyword in 1.4.0.
fallback = ModelFallbackMiddleware(bad, good)
print("fallback_models", [getattr(item, "model", type(item).__name__) for item in fallback.models])

desk = build_techcorp_desk(model=bad, middleware=[fallback])
out = run_ticket(
    desk,
    "Ticket TC-1002 for employee E-4102: VPN connects then drops. What should I check?",
    user_id="E-4102",
    thread_id="lab-5-16-fallback",
)
messages = out.get("messages") or []
last = messages[-1] if messages else None
print("fallback_reply", getattr(last, "content", last))

# %%
print("PLANTED WORLD FAULT: wrapper raises once, then delegates")


class FailOnceThenCall:
    """Planted world fault: the first model call raises, then it delegates."""

    def __init__(self, inner, box=None):
        self.inner = inner
        self.box = box if box is not None else {"calls": 0, "failures_left": 1}

    def bind_tools(self, tools, **kwargs):
        bound = self.inner.bind_tools(tools, **kwargs)
        return FailOnceThenCall(bound, box=self.box)

    def bind(self, **kwargs):
        bound = self.inner.bind(**kwargs)
        return FailOnceThenCall(bound, box=self.box)

    def invoke(self, messages, **kwargs):
        self.box["calls"] += 1
        if self.box["failures_left"] > 0:
            self.box["failures_left"] -= 1
            raise RuntimeError("planted world fault: first model call failed")
        return self.inner.invoke(messages, **kwargs)


box = {"calls": 0, "failures_left": 1}
wrapper = FailOnceThenCall(config.get_chat_model(), box=box)
retry = ModelRetryMiddleware(max_retries=2, initial_delay=0.1, backoff_factor=0.0, jitter=False)
retry_desk = build_techcorp_desk(model=wrapper, middleware=[retry])
retried = run_ticket(
    retry_desk,
    "Ticket TC-1001 for employee E-4101: please look up my account. Do not reset yet.",
    user_id="E-4101",
    thread_id="lab-5-16-retry",
)
retry_messages = retried.get("messages") or []
print("retry_calls", box["calls"])
print("retry_count", max(0, box["calls"] - 1))
print("retry_failures_left", box["failures_left"])
print("retry_reply", getattr(retry_messages[-1], "content", None) if retry_messages else None)
