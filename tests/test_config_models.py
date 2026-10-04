"""config.py picks a hosted model safely. Fake keys only, no network."""

import pytest
from langchain_core.messages import HumanMessage

import config

FAKE_ANTHROPIC_KEY = "sk-ant-fake-key-for-the-setup-lab"
FAKE_OPENAI_KEY = "sk-fake-key-for-the-setup-lab"


@pytest.fixture
def no_keys(monkeypatch):
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "OPENAI_CHAT_MODEL", "")
    monkeypatch.setattr(config, "ANTHROPIC_CHAT_MODEL", "")
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


def test_fable_gets_the_default_temperature_and_opus_keeps_zero(no_keys):
    no_keys.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC_KEY)
    no_keys.setattr(config, "ANTHROPIC_CHAT_MODEL", "claude-fable-5-1")
    assert config.get_chat_model().temperature is None
    no_keys.setattr(config, "ANTHROPIC_CHAT_MODEL", "claude-opus-5-5")
    assert config.get_chat_model().temperature == 0


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
