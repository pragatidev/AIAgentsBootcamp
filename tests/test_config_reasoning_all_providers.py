"""reasoning= and num_predict= mean the same thing on all four paths of config.get_chat_model.

Made-up keys only. Nothing is sent: each test builds the chat model and reads the request
body the library would send (Ollama's /api/chat params, OpenAI's and Anthropic's payload,
Google's generation config).
"""

import pytest
from langchain_core.messages import HumanMessage

import config

FAKE_KEY = "fake-key-for-the-reasoning-test"
HI = [HumanMessage(content="hi")]


@pytest.fixture
def only(monkeypatch):
    """Set one provider's made-up key and model id; clear the others."""
    for name in ("OPENAI", "ANTHROPIC", "GOOGLE"):
        monkeypatch.delenv(f"{name}_API_KEY", raising=False)
        monkeypatch.setattr(config, f"{name}_CHAT_MODEL", "")
    monkeypatch.setattr(config, "_warned_no_model_id", set())
    monkeypatch.setattr(config, "_warned_thinking", set())

    def use(provider: str, model: str) -> None:
        monkeypatch.setenv(f"{provider}_API_KEY", FAKE_KEY)
        monkeypatch.setattr(config, f"{provider}_CHAT_MODEL", model)

    return use


def openai_body(chat):
    return chat._get_request_payload(HI)


def anthropic_body(chat):
    return chat._get_request_payload(HI)


def google_config(chat):
    return chat._prepare_request(HI)["config"]


# --- the local path, unchanged -------------------------------------------------------------


def test_local_path_sends_think_false_and_the_cap(only):
    chat = config.get_chat_model(reasoning=False, num_predict=64)
    assert type(chat).__name__ == "ChatOllama"
    params = chat._chat_params([HumanMessage(content="hi")])
    assert params["think"] is False
    assert params["options"]["num_predict"] == 64


# --- OpenAI ---------------------------------------------------------------------------------


def test_openai_off_sends_effort_none_and_the_cap(only):
    only("OPENAI", "gpt-6-luna")
    chat = config.get_chat_model(reasoning=False, num_predict=64)
    assert type(chat).__name__ == "ChatOpenAI"
    body = openai_body(chat)
    assert body["reasoning_effort"] == "none"
    assert body["max_completion_tokens"] == 64


def test_openai_on_sends_effort_medium(only):
    only("OPENAI", "gpt-6-luna")
    body = openai_body(config.get_chat_model(reasoning=True))
    assert body["reasoning_effort"] == "medium"
    assert "max_completion_tokens" not in body


def test_openai_lowest_effort_is_low_on_astra_and_sol_with_one_warning(only, capsys):
    for model in ("gpt-6-astra", "gpt-6.1-sol"):
        only("OPENAI", model)
        config.get_chat_model(reasoning=False)
        body = openai_body(config.get_chat_model(reasoning=False))
        assert body["reasoning_effort"] == "low"
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 2
    assert all("cannot switch thinking off" in line for line in err)


def test_openai_gpt4_gets_the_cap_and_no_effort(only):
    only("OPENAI", "gpt-4.1-mini")
    body = openai_body(config.get_chat_model(reasoning=False, num_predict=64))
    assert "reasoning_effort" not in body
    assert body["max_completion_tokens"] == 64


# --- Anthropic ------------------------------------------------------------------------------


@pytest.mark.parametrize("model", ["claude-sonnet-5", "claude-haiku-5-5", "claude-opus-5", "claude-haiku-4-5-20251001"])
def test_anthropic_off_sends_disabled_and_the_cap(only, model):
    only("ANTHROPIC", model)
    body = anthropic_body(config.get_chat_model(reasoning=False, num_predict=64))
    assert body["thinking"] == {"type": "disabled"}
    assert body["max_tokens"] == 64


@pytest.mark.parametrize("model", ["claude-opus-5-5", "claude-fable-5-2", "claude-fable-5-1"])
def test_anthropic_models_that_cannot_switch_off_get_low_effort_and_say_so(only, capsys, model):
    only("ANTHROPIC", model)
    body = anthropic_body(config.get_chat_model(reasoning=False, num_predict=64))
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"] == {"effort": "low"}
    assert body["max_tokens"] == 64
    err = capsys.readouterr().err
    assert f"warning: {model} cannot switch thinking off" in err
    assert FAKE_KEY not in err


def test_anthropic_sonnet_5_5_off_sends_between_tools(only, capsys):
    only("ANTHROPIC", "claude-sonnet-5-5")
    body = anthropic_body(config.get_chat_model(reasoning=False))
    assert body["thinking"] == {"type": "between_tools"}
    assert "between_tools" in capsys.readouterr().err


def test_anthropic_on_sends_adaptive_and_no_temperature(only):
    only("ANTHROPIC", "claude-sonnet-4-6")
    body = anthropic_body(config.get_chat_model(reasoning=True))
    assert body["thinking"] == {"type": "adaptive"}
    assert "temperature" not in body and "temperature" not in body.get("extra_body", {})


def test_anthropic_budget_models_think_with_the_1024_minimum(only):
    only("ANTHROPIC", "claude-haiku-4-5-20251001")
    body = anthropic_body(config.get_chat_model(reasoning=True, num_predict=4096))
    assert body["thinking"] == {"type": "enabled", "budget_tokens": 1024}
    assert body["max_tokens"] == 4096
    with pytest.raises(ValueError, match="at least 1024"):
        config.get_chat_model(reasoning=True, num_predict=64)


def test_anthropic_left_out_is_unchanged(only):
    only("ANTHROPIC", "claude-opus-5-5")
    body = anthropic_body(config.get_chat_model())
    assert "thinking" not in body and "output_config" not in body


# --- Google ---------------------------------------------------------------------------------


def test_google_off_asks_for_the_lowest_level_and_the_cap(only, capsys):
    pytest.importorskip("langchain_google_genai")
    only("GOOGLE", "gemini-4-argon")
    cfg = google_config(config.get_chat_model(reasoning=False, num_predict=64))
    assert cfg.max_output_tokens == 64
    assert cfg.thinking_config.thinking_level.value == "LOW"
    assert "gemini-4-argon cannot switch thinking off" in capsys.readouterr().err


def test_google_minimal_where_the_model_takes_it(only):
    pytest.importorskip("langchain_google_genai")
    only("GOOGLE", "gemini-3.6-flash")
    cfg = google_config(config.get_chat_model(reasoning=False))
    assert cfg.thinking_config.thinking_level.value == "MINIMAL"


def test_google_flash_lite_is_off_unless_asked(only):
    pytest.importorskip("langchain_google_genai")
    only("GOOGLE", "gemini-2.5-flash-lite")
    assert google_config(config.get_chat_model(reasoning=False)).thinking_config is None
    cfg = google_config(config.get_chat_model(reasoning=True))
    assert cfg.thinking_config.thinking_level.value == "MEDIUM"


def test_google_left_out_is_unchanged(only):
    pytest.importorskip("langchain_google_genai")
    only("GOOGLE", "gemini-4-argon")
    cfg = google_config(config.get_chat_model())
    assert cfg.thinking_config is None
    assert cfg.max_output_tokens is None


# --- the same cap on all four ---------------------------------------------------------------


def _cap(chat) -> int:
    kind = type(chat).__name__
    if kind == "ChatOllama":
        return chat._chat_params(HI)["options"]["num_predict"]
    if kind == "ChatOpenAI":
        return openai_body(chat)["max_completion_tokens"]
    if kind == "ChatAnthropic":
        return anthropic_body(chat)["max_tokens"]
    return google_config(chat).max_output_tokens


@pytest.mark.parametrize(
    "provider, model",
    [(None, None), ("OPENAI", "gpt-6-luna"), ("ANTHROPIC", "claude-sonnet-5"), ("GOOGLE", "gemini-4-argon")],
)
def test_num_predict_is_the_same_cap_on_every_path(only, provider, model):
    if provider == "GOOGLE":
        pytest.importorskip("langchain_google_genai")
    if provider:
        only(provider, model)
    assert _cap(config.get_chat_model(reasoning=False, num_predict=64)) == 64
