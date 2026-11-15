"""config.py picks a hosted model safely. Fake keys only, no network."""

import pytest
from langchain_core.messages import HumanMessage

import config

FAKE_ANTHROPIC_KEY = "sk-ant-fake-key-for-the-setup-lab"
FAKE_OPENAI_KEY = "sk-fake-key-for-the-setup-lab"


@pytest.fixture
def no_keys(monkeypatch):
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "OPENAI_CHAT_MODEL", "")
    monkeypatch.setattr(config, "ANTHROPIC_CHAT_MODEL", "")
    monkeypatch.setattr(config, "GOOGLE_CHAT_MODEL", "", raising=False)
    monkeypatch.setattr(config, "_warned_no_model_id", set(), raising=False)
    return monkeypatch


@pytest.mark.parametrize(
    "model_id",
    ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5-20251001"],
)
def test_anthropic_request_builds_for_every_current_model(no_keys, model_id):
    no_keys.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC_KEY)
    no_keys.setattr(config, "ANTHROPIC_CHAT_MODEL", model_id)
    chat = config.get_chat_model()
    assert type(chat).__name__ == "ChatAnthropic"
    # Builds the request body locally. This is where the library raised
    # "`temperature` is not supported ... at non-default values".
    payload = chat._get_request_payload([HumanMessage(content="hi")])
    assert payload["model"] == model_id


def test_new_claude_models_get_the_default_temperature_and_older_ones_keep_zero(no_keys):
    # Claude's thinking docs (read 2026-11-15): Fable, Mythos, Opus 5.5, Opus 5, Opus 4.8, Opus 4.7,
    # Sonnet 5.5, Sonnet 5 and Haiku 5.5 answer 400 to any non-default temperature.
    no_keys.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC_KEY)
    for model_id in ("claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"):
        no_keys.setattr(config, "ANTHROPIC_CHAT_MODEL", model_id)
        chat = config.get_chat_model()
        assert chat.temperature is None, model_id
        body = chat._get_request_payload([HumanMessage(content="hi")])
        assert "temperature" not in body and "temperature" not in body.get("extra_body", {}), model_id
    for model_id in ("claude-sonnet-4-6", "claude-haiku-4-5-20251001"):
        no_keys.setattr(config, "ANTHROPIC_CHAT_MODEL", model_id)
        assert config.get_chat_model().temperature == 0, model_id


@pytest.mark.parametrize(
    "key_name, key_value",
    [("OPENAI_API_KEY", FAKE_OPENAI_KEY), ("ANTHROPIC_API_KEY", FAKE_ANTHROPIC_KEY)],
)
def test_key_without_model_id_warns_once(no_keys, capsys, key_name, key_value):
    no_keys.setenv(key_name, key_value)
    provider = key_name.split("_")[0]
    first = config.get_chat_model()
    config.get_chat_model()
    err = capsys.readouterr().err.strip().splitlines()
    assert type(first).__name__ == "ChatOllama"
    assert len(err) == 1
    assert f"{provider}_API_KEY is set but {provider}_CHAT_MODEL is empty" in err[0]
    assert key_value not in err[0]


def test_local_default_has_no_warning_and_temperature_zero(no_keys, capsys):
    chat = config.get_chat_model()
    assert type(chat).__name__ == "ChatOllama"
    assert chat.model == config.CHAT_MODEL
    assert chat.temperature == 0
    assert capsys.readouterr().err == ""


FAKE_GOOGLE_KEY = "fake-google-key-for-the-setup-lab"


def test_google_key_and_model_build_gemini(no_keys):
    pytest.importorskip("langchain_google_genai")
    no_keys.setenv("GOOGLE_API_KEY", FAKE_GOOGLE_KEY)
    no_keys.setattr(config, "GOOGLE_CHAT_MODEL", "gemini-test-model")
    chat = config.get_chat_model()
    assert type(chat).__name__ == "ChatGoogleGenerativeAI"
    assert "gemini-test-model" in chat.model
    assert chat.temperature == 0
    assert config.has_live_key()


def test_google_key_without_model_warns_and_stays_local(no_keys, capsys):
    no_keys.setenv("GOOGLE_API_KEY", FAKE_GOOGLE_KEY)
    chat = config.get_chat_model()
    assert type(chat).__name__ == "ChatOllama"
    assert "GOOGLE_CHAT_MODEL is empty" in capsys.readouterr().err


def test_force_local_ignores_a_google_key(no_keys):
    no_keys.setenv("GOOGLE_API_KEY", FAKE_GOOGLE_KEY)
    no_keys.setattr(config, "GOOGLE_CHAT_MODEL", "gemini-test-model")
    assert type(config.get_chat_model(force_local=True)).__name__ == "ChatOllama"
