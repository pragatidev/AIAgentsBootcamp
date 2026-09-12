"""S5 live labs skip without a key or a local server."""

import config
from dataflow.llm import ping_hosted, ping_local


def test_hosted_skips_without_key():
    if config.has_live_key():
        return
    out = ping_hosted()
    assert out["skipped"] is True
    assert "key" in out["reason"]


def test_local_skips_or_reports_model():
    out = ping_local()
    assert "skipped" in out
    if out["skipped"]:
        assert out["reason"] == "no local model"
