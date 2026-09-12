"""11.2 PII export has no sk- key. Pytest stays green with no Ollama."""

import os
from pathlib import Path

from langchain_core.messages import AIMessage

from dataflow.guardrails.pii import export_trace, run_pii_ticket
from tests.fixtures.fake_model import ScriptedToolChatModel


def test_export_has_no_sk_key(tmp_path):
    path = os.environ.get("DATAFLOW_PII_EXPORT", "").strip()
    if path:
        text = Path(path).read_text(encoding="utf-8")
    else:
        model = ScriptedToolChatModel(script=[AIMessage(content="I can help with the order.")])
        out = run_pii_ticket(
            "Hi jordan@dataflow.example, key sk-abcdefghijklmnopqrstuvwxyz1234",
            model=model,
            secret_filter=True,
        )
        dest = tmp_path / "pii.jsonl"
        export_trace(dest, out["messages"])
        text = dest.read_text(encoding="utf-8")
    assert "sk-" not in text
