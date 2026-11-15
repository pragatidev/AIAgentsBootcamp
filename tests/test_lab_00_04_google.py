"""Lab 00.04 checks Google the same way as OpenAI and Anthropic. Fake keys, stub models, no network.

Kept apart from test_lab_00_04.py so that file still collects the 8 items lecture 1.10 shows.
"""

import pytest

import config
from test_lab_00_04 import _StubHosted, lab  # noqa: F401  (lab is the shared fixture)

FAKE_GOOGLE_KEY = "fake-google-key-for-the-setup-lab"


def test_google_key_without_model_id_says_the_model_id_is_empty(lab):  # noqa: F811
    lab.monkeypatch.setenv("GOOGLE_API_KEY", FAKE_GOOGLE_KEY)
    out = lab()
    assert out[4:] == [
        "hosted skipped: GOOGLE_API_KEY is set but GOOGLE_CHAT_MODEL is empty, "
        "so there is no hosted model to call. Set the model id in .env."
    ]
    assert not any(FAKE_GOOGLE_KEY in line for line in out)


def test_google_key_and_model_id_run_the_hosted_cell(lab):  # noqa: F811
    lab.monkeypatch.setenv("GOOGLE_API_KEY", FAKE_GOOGLE_KEY)
    lab.monkeypatch.setattr(config, "GOOGLE_CHAT_MODEL", "gemini-fake")
    lab.monkeypatch.setattr(config, "get_chat_model", lambda **kwargs: _StubHosted())
    out = lab()
    assert out[4:] == [
        "hosted_model gemini-fake",
        "hosted_reply a stub hosted reply",
        "ran hosted then local",
    ]
    assert not any(FAKE_GOOGLE_KEY in line for line in out)


@pytest.mark.parametrize("first", ["OPENAI", "ANTHROPIC"])
def test_an_earlier_provider_with_its_model_wins_over_google(lab, first):  # noqa: F811
    lab.monkeypatch.setenv(f"{first}_API_KEY", "a-made-up-key")
    lab.monkeypatch.setattr(config, f"{first}_CHAT_MODEL", f"{first.lower()}-fake")
    lab.monkeypatch.setenv("GOOGLE_API_KEY", FAKE_GOOGLE_KEY)
    lab.monkeypatch.setattr(config, "GOOGLE_CHAT_MODEL", "gemini-fake")
    lab.monkeypatch.setattr(config, "get_chat_model", lambda **kwargs: _StubHosted())
    out = lab()
    assert out[4] == f"hosted_model {first.lower()}-fake"
