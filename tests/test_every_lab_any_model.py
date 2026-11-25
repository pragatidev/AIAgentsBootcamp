"""Which model a lab runs on. On this branch the memory labs follow .env; the raw-wire, window and context labs stay local.

Made-up keys only. Nothing is sent: hosted models are built and their request bodies read.
"""

import re
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

import config
from dataflow.context import agent

ROOT = Path(__file__).resolve().parents[1]
FAKE_KEY = "fake-key-for-the-any-model-test"
PAIRS = {"OPENAI": "gpt-6-luna", "ANTHROPIC": "claude-sonnet-5", "GOOGLE": "gemini-3.6-flash"}


@pytest.fixture
def only(monkeypatch):
    """No hosted pair, then one provider's made-up pair on request."""
    for name in PAIRS:
        monkeypatch.delenv(f"{name}_API_KEY", raising=False)
        monkeypatch.setattr(config, f"{name}_CHAT_MODEL", "")
    monkeypatch.setattr(config, "_warned_no_model_id", set())
    monkeypatch.setattr(config, "_warned_thinking", set())
    monkeypatch.setattr(config, "_noted_local", set())

    def use(provider: str) -> None:
        monkeypatch.setenv(f"{provider}_API_KEY", FAKE_KEY)
        monkeypatch.setattr(config, f"{provider}_CHAT_MODEL", PAIRS[provider])

    return use


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


# --- the context helpers stay local on this branch ----------------------------------------------


@pytest.mark.parametrize("provider", list(PAIRS))
def test_chat_caller_stays_local_and_says_why_once(only, provider, monkeypatch, capsys):
    only(provider)
    seen = []
    monkeypatch.setattr(config, "get_local_chat_model", lambda **kw: seen.append(kw) or object())
    agent.chat_caller()
    agent.chat_caller()
    assert seen == [{"reasoning": False, "num_predict": 80}] * 2
    err = capsys.readouterr().err
    assert err.count("note: this lab runs on the local model") == 1
    assert "share one caller with the context rot lab" in err and FAKE_KEY not in err


def test_chat_caller_is_silent_on_a_local_run(only, monkeypatch, capsys):
    monkeypatch.setattr(config, "get_local_chat_model", lambda **kw: object())
    agent.chat_caller()
    assert capsys.readouterr() == ("", "")


def test_summariser_stays_local_with_the_desk(only, monkeypatch):
    only("OPENAI")

    class Model:
        def invoke(self, messages):
            return type("R", (), {"content": "facts: DF-1001."})()

    monkeypatch.setattr(config, "get_local_chat_model", lambda **kw: Model())
    monkeypatch.setattr(config, "get_chat_model", lambda **kw: pytest.fail("the summariser runs with the local desk"))
    assert agent.default_summariser("older turns") == "facts: DF-1001."


# --- the memory labs follow .env ------------------------------------------------------------------


@pytest.mark.parametrize("name,line", [("04_03_thread_memory.py", 33), ("04_03_other_thread_break.py", 38), ("04_10_desk_remembers.py", 30)])
def test_memory_labs_build_the_configured_model(name, line):
    text = (ROOT / "labs" / name).read_text(encoding="utf-8").splitlines()[line - 1]
    assert "config.get_chat_model(reasoning=False, num_predict=80)" in text


@pytest.mark.parametrize("provider", list(PAIRS))
def test_get_chat_model_for_a_memory_lab_carries_the_cap(only, provider):
    only(provider)
    chat = config.get_chat_model(reasoning=False, num_predict=80)
    if provider == "GOOGLE":
        assert chat._prepare_request([HumanMessage(content="hi")])["config"].max_output_tokens == 80
    else:
        body = chat._get_request_payload([HumanMessage(content="hi")])
        assert body["model"] == PAIRS[provider]
        assert body.get("max_completion_tokens", body.get("max_tokens")) == 80


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
    allowed = {"00_04_keys_and_config.py", "01_04_tokens_and_window.py", "01_08_structured_output_raw.py", "01_14_swap_the_model.py"}
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
