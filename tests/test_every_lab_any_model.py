"""Which model a lab runs on: the context and memory helpers follow .env, the raw-wire and window labs stay local.

Made-up keys only. Nothing is sent: hosted models are built and their request bodies read, and the
one Ollama endpoint applied_window reads is replaced by a stub.
"""

import io
import json
import re
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages.utils import convert_to_messages

import config
from dataflow.context import agent

ROOT = Path(__file__).resolve().parents[1]
FAKE_KEY = "fake-key-for-the-any-model-test"
PAIRS = {"OPENAI": "gpt-6-luna", "ANTHROPIC": "claude-sonnet-5", "GOOGLE": "gemini-3.6-flash"}
# What ContextAgent sends back after a tool call: OpenAI-shaped dicts.
HISTORY = [
    {"role": "system", "content": "desk"},
    {"role": "user", "content": "return window?"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "return_policy.md"}'}}
        ],
    },
    {"role": "tool", "tool_call_id": "c1", "content": '{"found": true}'},
]


@pytest.fixture
def only(monkeypatch):
    """No hosted pair, then one provider's made-up pair on request."""
    for name in PAIRS:
        monkeypatch.delenv(f"{name}_API_KEY", raising=False)
        monkeypatch.setattr(config, f"{name}_CHAT_MODEL", "")
    monkeypatch.setattr(config, "_warned_no_model_id", set())
    monkeypatch.setattr(config, "_warned_thinking", set())
    monkeypatch.setattr(config, "_noted_local", set())
    monkeypatch.setattr(agent.chat_caller, "ran_local", False)

    def use(provider: str) -> None:
        monkeypatch.setenv(f"{provider}_API_KEY", FAKE_KEY)
        monkeypatch.setattr(config, f"{provider}_CHAT_MODEL", PAIRS[provider])

    return use


@pytest.fixture
def built(monkeypatch):
    """Every chat model config.get_chat_model builds, in order."""
    out = []
    real = config.get_chat_model

    def capture(**kw):
        out.append(real(**kw))
        return out[-1]

    monkeypatch.setattr(config, "get_chat_model", capture)
    return out


# --- the three helpers ------------------------------------------------------------------------


def test_no_pair_is_local(only):
    assert config.hosted_choice() is None
    assert config.chat_model_id() == config.CHAT_MODEL


def test_a_key_without_its_model_id_is_local(only, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    assert config.hosted_choice() is None
    assert config.chat_model_id() == config.CHAT_MODEL


@pytest.mark.parametrize("provider,kind", [("OPENAI", "ChatOpenAI"), ("ANTHROPIC", "ChatAnthropic"), ("GOOGLE", "ChatGoogleGenerativeAI")])
def test_hosted_choice_names_what_get_chat_model_builds(only, provider, kind):
    only(provider)
    assert config.hosted_choice() == (provider, PAIRS[provider])
    assert config.chat_model_id() == PAIRS[provider]
    assert type(config.get_chat_model()).__name__ == kind


def test_hosted_choice_keeps_get_chat_model_order(only):
    only("GOOGLE")
    only("ANTHROPIC")
    assert config.hosted_choice() == ("ANTHROPIC", PAIRS["ANTHROPIC"])
    only("OPENAI")
    assert config.hosted_choice() == ("OPENAI", PAIRS["OPENAI"])
    assert type(config.get_chat_model()).__name__ == "ChatOpenAI"


def test_local_on_purpose_is_silent_on_a_local_run(only, capsys):
    config.local_on_purpose("a reason")
    assert capsys.readouterr() == ("", "")


def test_local_on_purpose_says_why_once_on_stderr_with_no_key(only, capsys):
    only("GOOGLE")
    config.local_on_purpose("a reason")
    config.local_on_purpose("a reason")
    out, err = capsys.readouterr()
    assert out == ""
    assert err.splitlines() == [
        f"note: this lab runs on the local model {config.CHAT_MODEL} on purpose, "
        "not on your GOOGLE model gemini-3.6-flash: a reason"
    ]
    assert FAKE_KEY not in err


# --- chat_caller, context_caller and the summariser ---------------------------------------------


def test_chat_caller_is_unchanged_on_a_local_run(only, built):
    call = agent.chat_caller(num_predict=80)
    chat = built[-1]
    assert type(chat).__name__ == "ChatOllama"
    assert chat.model_dump() == config.get_local_chat_model(reasoning=False, num_predict=80).model_dump()
    assert call.model == config.CHAT_MODEL


@pytest.mark.parametrize("provider", list(PAIRS))
def test_chat_caller_follows_env_with_the_cap_and_no_window(only, built, provider, capsys):
    only(provider)
    call = agent.chat_caller(num_predict=80)
    chat = built[-1]
    assert call.model == PAIRS[provider]
    if provider == "GOOGLE":
        cfg = chat._prepare_request(convert_to_messages(HISTORY[:2]))["config"]
        assert cfg.max_output_tokens == 80
    else:
        body = chat._get_request_payload(convert_to_messages(HISTORY[:2]))
        assert body["model"] == PAIRS[provider]
        assert body.get("max_completion_tokens", body.get("max_tokens")) == 80
        assert "num_ctx" not in json.dumps(body)
    assert "note:" not in capsys.readouterr().err


@pytest.mark.parametrize("provider", list(PAIRS))
def test_chat_caller_with_num_ctx_stays_local_and_says_why(only, provider, capsys):
    only(provider)
    seen = []
    real = config.get_local_chat_model
    call = None
    try:
        config.get_local_chat_model = lambda **kw: seen.append(real(**kw)) or seen[-1]
        call = agent.chat_caller(num_ctx=512)
        agent.chat_caller(num_ctx=512)
    finally:
        config.get_local_chat_model = real
    assert type(seen[0]).__name__ == "ChatOllama" and seen[0].num_ctx == 512
    assert call.model == config.CHAT_MODEL
    err = capsys.readouterr().err
    assert err.count("note: this lab runs on the local model") == 1
    assert "sets the context window (num_ctx)" in err and FAKE_KEY not in err


def test_chat_caller_local_keeps_the_server_window_on_the_local_model(only, capsys):
    """03_02's run A: no window set, but the lab compares windows on one model, so it stays local."""
    only("GOOGLE")
    seen = []
    real = config.get_local_chat_model
    try:
        config.get_local_chat_model = lambda **kw: seen.append(kw) or real(**kw)
        call = agent.chat_caller(num_ctx=None, local=True)
    finally:
        config.get_local_chat_model = real
    assert seen == [{"reasoning": False, "num_predict": 80}]
    assert call.model == config.CHAT_MODEL and agent.chat_caller.ran_local is True
    assert "sets the context window (num_ctx)" in capsys.readouterr().err


def test_rot_lab_runs_both_windows_on_the_local_model():
    text = (ROOT / "labs" / "03_02_context_rot.py").read_text(encoding="utf-8")
    assert "ContextAgent(chat_caller(num_ctx=window, local=True), system=SYSTEM)" in text


@pytest.mark.parametrize("provider", list(PAIRS))
def test_context_caller_history_makes_a_tool_call_body(only, built, provider):
    """ContextAgent's OpenAI-shaped history becomes each provider's own tool-call shape."""
    only(provider)
    agent.context_caller(enable_read=True, enable_notes=False)
    chat = built[-1]
    binding = chat.bind_tools([agent.READ_SCHEMA])
    messages = convert_to_messages(HISTORY)
    if provider == "GOOGLE":
        req = chat._prepare_request(messages, **binding.kwargs)
        parts = [p for c in req["contents"] for p in c.parts]
        assert any(p.function_call and p.function_call.name == "read_file" for p in parts)
        assert any(p.function_response and p.function_response.name == "read_file" for p in parts)
        assert req["config"].max_output_tokens == 512
        return
    body = chat._get_request_payload(messages, **binding.kwargs)
    text = json.dumps(body)
    assert body.get("max_completion_tokens", body.get("max_tokens")) == 512
    if provider == "OPENAI":
        assert body["messages"][2]["tool_calls"][0]["id"] == "c1"
        assert body["messages"][3] == {"content": '{"found": true}', "role": "tool", "tool_call_id": "c1"}
        assert body["tools"][0]["function"]["name"] == "read_file"
    else:
        assert body["system"] == "desk"
        assert body["messages"][1]["content"][0]["type"] == "tool_use" and body["messages"][1]["content"][0]["id"] == "c1"
        assert body["messages"][2]["content"][0]["type"] == "tool_result" and body["messages"][2]["content"][0]["tool_use_id"] == "c1"
        assert body["tools"][0]["name"] == "read_file"
    assert FAKE_KEY not in text


def test_chat_caller_reads_text_from_a_list_content_reply(only, monkeypatch):
    class Model:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(
                content=[{"type": "text", "text": "Thirty days."}, {"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "x"}}],
                tool_calls=[{"name": "read_file", "args": {"path": "x"}, "id": "t1", "type": "tool_call"}],
            )

    monkeypatch.setattr(config, "get_chat_model", lambda **kw: Model())
    out = agent.context_caller(enable_read=True, enable_notes=False)([{"role": "user", "content": "hi"}])
    assert out["content"] == "Thirty days."
    assert out["tool_calls"] == [{"id": "t1", "name": "read_file", "arguments": {"path": "x"}}]


def test_summariser_follows_env_and_reads_text(only, monkeypatch):
    seen = {}

    class Model:
        def invoke(self, messages):
            return AIMessage(content=[{"type": "text", "text": "facts: DF-1001."}], usage_metadata={"input_tokens": 5, "output_tokens": 2, "total_tokens": 7})

    monkeypatch.setattr(config, "get_chat_model", lambda **kw: seen.update(kw) or Model())
    monkeypatch.setattr(config, "get_local_chat_model", lambda **kw: pytest.fail("the summariser should follow .env"))
    summary, usage = agent.summarise_with_usage("older turns")
    assert summary == "facts: DF-1001."
    assert usage["input_tokens"] == 5
    assert seen == {"reasoning": False, "num_predict": 160}


# --- applied_window -----------------------------------------------------------------------------


def _ps(monkeypatch, ctx=4096):
    import urllib.request

    calls = []
    payload = json.dumps({"models": [{"name": config.CHAT_MODEL, "model": config.CHAT_MODEL, "context_length": ctx}]})
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=10: calls.append(url) or io.BytesIO(payload.encode("utf-8")))
    return calls


def test_applied_window_reads_ollama_on_a_local_run(only, monkeypatch):
    calls = _ps(monkeypatch)
    assert agent.applied_window() == 4096
    assert calls == [config._ollama_base() + "/api/ps"]


def test_applied_window_is_none_when_the_run_went_hosted(only, monkeypatch):
    calls = _ps(monkeypatch)
    only("GOOGLE")
    assert agent.applied_window() is None
    assert calls == []


def test_applied_window_counts_a_window_lab_that_stayed_local(only, monkeypatch):
    calls = _ps(monkeypatch, ctx=512)
    only("OPENAI")
    monkeypatch.setattr(config, "get_local_chat_model", lambda **kw: object())
    agent.chat_caller(num_ctx=512)
    assert agent.applied_window() == 512
    assert len(calls) == 1


# --- the scratch agent's raw caller -------------------------------------------------------------


def test_scratch_caller_stays_local_and_says_why_once(only, monkeypatch, capsys):
    import openai

    from techcorp.agent import scratch

    clients = []
    monkeypatch.setattr(openai, "OpenAI", lambda **kw: clients.append(kw) or object())
    only("ANTHROPIC")
    scratch.openai_caller([])
    scratch.openai_caller([])
    err = capsys.readouterr().err
    assert err.count("note: this lab runs on the local model") == 1
    assert "the scratch agent speaks the raw OpenAI wire to Ollama's /v1" in err
    assert clients == [{"base_url": config._ollama_base() + "/v1", "api_key": "ollama"}] * 2


def test_scratch_caller_is_silent_and_passes_through_on_a_local_run(only, monkeypatch, capsys):
    from techcorp.agent import scratch

    seen = []
    monkeypatch.setattr(scratch, "_raw_openai_caller", lambda tools, model_id=None: seen.append((tools, model_id)) or "caller")
    assert scratch.openai_caller(["t"], "m") == "caller"
    assert seen == [(["t"], "m")]
    assert capsys.readouterr() == ("", "")


# --- the labs -------------------------------------------------------------------------------


STAY_LOCAL = {
    "01_04_tokens_and_window.py": "it reads and sets Ollama's own context window (num_ctx)",
    "01_06_first_raw_api_call.py": "its raw calls speak the OpenAI wire to Ollama's /v1 and read the thinking",
    "01_08_structured_output_raw.py": "its raw calls speak the OpenAI wire to Ollama's /v1, and its JSON fallback",
    "01_10_raw_tool_call.py": "it sends a raw tool call to Ollama's /v1 so you can read every field",
}


@pytest.mark.parametrize("name", sorted(STAY_LOCAL))
def test_raw_and_window_labs_end_with_the_note(name):
    lines = (ROOT / "labs" / name).read_text(encoding="utf-8").splitlines()
    assert lines[-1].startswith("config.local_on_purpose(")
    assert STAY_LOCAL[name] in lines[-1]
    assert sum("local_on_purpose" in line for line in lines) == 1


def test_only_the_labs_that_stay_local_build_the_local_model():
    """Past the keys lab, the swap lab and 4.16, a lab that builds a model with get_local_chat_model stays local on purpose."""
    allowed = {"00_04_keys_and_config.py", "01_04_tokens_and_window.py", "01_08_structured_output_raw.py",
               "01_14_swap_the_model.py", "05_16_model_fallback_and_retries.py"}
    found = {p.name for p in (ROOT / "labs").glob("*.py") if "get_local_chat_model(" in p.read_text(encoding="utf-8")}
    assert found == allowed


def test_no_lab_label_prints_the_local_id_when_a_hosted_model_ran():
    label = re.compile(r'print\(\s*"model(_from_config)?",\s*config\.CHAT_MODEL|"model_id": config\.CHAT_MODEL')
    hits = [
        p.relative_to(ROOT).as_posix()
        for p in list((ROOT / "labs").glob("*.py")) + [ROOT / "research_agent" / "__main__.py"]
        if not p.name.startswith("16_") and label.search(p.read_text(encoding="utf-8"))
    ]
    assert hits == []
