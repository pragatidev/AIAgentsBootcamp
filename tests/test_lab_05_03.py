"""Lab 05.03, read_usage typed by the student. A scripted model stands in for the real one here, and only here."""

import runpy
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, SystemMessage

import config
from techcorp.agent.usage import read_usage

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_03_init_chat_model.py"

KNOWN = AIMessage(
    content="Your reset is on its way. Ticket ID: TC-1001.",
    usage_metadata={"input_tokens": 58, "output_tokens": 182, "total_tokens": 240},
    additional_kwargs={"reasoning_content": "x" * 400},
)


class Recorder:
    model = "scripted"

    def __init__(self) -> None:
        self.seen: list[list] = []

    def invoke(self, messages, **kwargs):
        self.seen.append(list(messages))
        return KNOWN


@pytest.fixture
def run_lab(monkeypatch, capsys):
    calls: list[dict] = []
    recorder = Recorder()

    def fake_get_chat_model(**kwargs):
        calls.append(kwargs)
        return recorder

    monkeypatch.setattr(config, "get_chat_model", fake_get_chat_model)
    lab = runpy.run_path(str(LAB), run_name="__main__")
    return lab, calls, recorder, capsys.readouterr().out.splitlines()


def test_lab_uses_config_door(run_lab):
    _, calls, _, out = run_lab
    assert calls == [{"reasoning": True}]
    assert out[0] == "chat_model_class Recorder"
    assert "blocks ['reasoning', 'text']" in out and "visible_words 9" in out


def test_read_usage_typed_matches_shipped(run_lab):
    lab = run_lab[0]
    expected = {
        "input_tokens": 58,
        "output_tokens": 182,
        "total_tokens": 240,
        "blocks": ["reasoning", "text"],
        "reasoning_chars": 400,
        "visible_words": 9,
    }
    assert lab["read_usage"](KNOWN) == read_usage(KNOWN) == expected
    bare = AIMessage(content="hi")
    assert lab["read_usage"](bare) == read_usage(bare)
    assert lab["read_usage"](bare)["total_tokens"] == 0


def test_rules_go_in_the_system_slot(run_lab):
    first = run_lab[2].seen[0]
    assert isinstance(first[0], SystemMessage)
    assert "Always end with the ticket id" in first[0].content


def test_init_chat_model_builds_the_same_local_class():
    # Construction only, no call. The one-liner skips config's base_url and num_predict cap.
    from langchain.chat_models import init_chat_model

    one_liner = init_chat_model("ollama:" + config.CHAT_MODEL, temperature=0)
    door = config.get_chat_model(force_local=True)
    assert type(one_liner).__name__ == type(door).__name__ == "ChatOllama"
    assert one_liner.model == door.model == config.CHAT_MODEL
    assert door.num_predict == config.NUM_PREDICT and one_liner.num_predict is None
