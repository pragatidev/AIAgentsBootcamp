"""Lab 00.04 says why the hosted call skipped. Fake keys, a stub local model, no network."""

import runpy
from pathlib import Path

import httpx
import pytest

import config

LAB = Path(__file__).resolve().parents[1] / "labs" / "00_04_keys_and_config.py"
FAKE_OPENAI_KEY = "sk-fake-key-for-the-setup-lab"
FAKE_ANTHROPIC_KEY = "sk-ant-fake-key-for-the-setup-lab"


class _StubLocal:
    def invoke(self, prompt):
        return "a stub reply"


def _no_hosted_call(**kwargs):
    raise AssertionError("the lab must not build a hosted model here")


@pytest.fixture
def lab(monkeypatch, capsys):
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "OPENAI_CHAT_MODEL", "")
    monkeypatch.setattr(config, "ANTHROPIC_CHAT_MODEL", "")
    monkeypatch.setattr(config, "get_local_chat_model", lambda **kwargs: _StubLocal())
    monkeypatch.setattr(config, "get_chat_model", _no_hosted_call)

    def run() -> list[str]:
        runpy.run_path(str(LAB), run_name="__main__")
        return capsys.readouterr().out.splitlines()

    run.monkeypatch = monkeypatch
    return run


def test_no_key_output_is_unchanged(lab):
    out = lab()
    assert out == [
        f"chat_model_id {config.CHAT_MODEL}",
        "ids_live_in config.py",
        f"local_model {config.CHAT_MODEL}",
        "local_reply a stub reply",
        "hosted skipped: no cloud key set",
    ]


@pytest.mark.parametrize(
    "provider, key_value",
    [("OPENAI", FAKE_OPENAI_KEY), ("ANTHROPIC", FAKE_ANTHROPIC_KEY)],
)
def test_key_without_model_id_says_the_model_id_is_empty(lab, provider, key_value):
    lab.monkeypatch.setenv(f"{provider}_API_KEY", key_value)
    out = lab()
    assert out[:4] == [
        f"chat_model_id {config.CHAT_MODEL}",
        "ids_live_in config.py",
        f"local_model {config.CHAT_MODEL}",
        "local_reply a stub reply",
    ]
    assert out[4:] == [
        f"hosted skipped: {provider}_API_KEY is set but {provider}_CHAT_MODEL is empty, "
        "so there is no hosted model to call. Set the model id in .env."
    ]
    assert not any("no cloud key set" in line for line in out)
    assert not any(key_value in line for line in out)


def test_a_model_id_under_the_other_key_does_not_count(lab):
    # OPENAI_CHAT_MODEL is set, but the only key is Anthropic's: get_chat_model
    # would run the local model, so the lab must not claim a hosted run.
    lab.monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC_KEY)
    lab.monkeypatch.setattr(config, "OPENAI_CHAT_MODEL", "gpt-fake")
    out = lab()
    assert out[-1].startswith("hosted skipped: ANTHROPIC_API_KEY is set but ANTHROPIC_CHAT_MODEL is empty")


# What a closed port raises. ChatOllama's streaming path lets httpx's error out
# (captures_313/10); the ollama client's other paths wrap it in ConnectionError.
UNREACHABLE = [
    httpx.ConnectError("[WinError 10061] No connection could be made"),
    ConnectionError("Failed to connect to Ollama."),
]


class _UnreachableLocal:
    def __init__(self, error):
        self.error = error

    def invoke(self, prompt):
        raise self.error


class _StubHosted:
    def invoke(self, prompt):
        return "a stub hosted reply"


def _local_skipped_line() -> str:
    return (
        f"local skipped: nothing answered at {config.OLLAMA_BASE_URL}. Is Ollama installed and running? "
        'See TROUBLESHOOTING.md, "The local model cannot be reached".'
    )


@pytest.mark.parametrize("error", UNREACHABLE, ids=["httpx_ConnectError", "ConnectionError"])
def test_unreachable_local_model_skips_to_the_hosted_cell(lab, error):
    lab.monkeypatch.setattr(config, "get_local_chat_model", lambda **kwargs: _UnreachableLocal(error))
    lab.monkeypatch.setenv("OPENAI_API_KEY", FAKE_OPENAI_KEY)
    lab.monkeypatch.setattr(config, "OPENAI_CHAT_MODEL", "gpt-fake")
    lab.monkeypatch.setattr(config, "get_chat_model", lambda **kwargs: _StubHosted())
    out = lab()
    assert out == [
        f"chat_model_id {config.CHAT_MODEL}",
        "ids_live_in config.py",
        _local_skipped_line(),
        "hosted_model gpt-fake",
        "hosted_reply a stub hosted reply",
        "ran hosted, local skipped",
    ]
    assert not any(FAKE_OPENAI_KEY in line for line in out)


def test_unreachable_local_model_with_no_key_ends_cleanly(lab):
    lab.monkeypatch.setattr(config, "get_local_chat_model", lambda **kwargs: _UnreachableLocal(UNREACHABLE[0]))
    out = lab()
    assert out == [
        f"chat_model_id {config.CHAT_MODEL}",
        "ids_live_in config.py",
        _local_skipped_line(),
        "hosted skipped: no cloud key set",
    ]


def test_other_local_errors_are_not_swallowed(lab):
    # Only "nothing answered" is caught. A model that is not pulled, or any
    # other fault, still stops the lab with its own error.
    lab.monkeypatch.setattr(config, "get_local_chat_model", lambda **kwargs: _UnreachableLocal(ValueError("boom")))
    with pytest.raises(ValueError, match="boom"):
        lab()
