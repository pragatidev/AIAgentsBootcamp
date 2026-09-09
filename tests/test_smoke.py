"""Clone contract. No API key."""

from pathlib import Path

import config
from northstar.agent.loop import run_loop
from northstar.serve.app import health
from northstar.tools.escalate import escalate_to_human
from northstar.tools.orders import lookup_order
from northstar.tools.policy import read_policy

ROOT = Path(__file__).resolve().parents[1]


def test_wiki_and_orders_exist():
    assert (ROOT / "northstar" / "wiki" / "return_policy.md").is_file()
    assert (ROOT / "northstar" / "data" / "orders.json").is_file()
    assert (ROOT / "docs" / "CURRENCY.md").is_file()
    assert (ROOT / "config.py").is_file()


def test_config_has_local_default_and_import_does_not_need_a_key():
    assert config.CHAT_MODEL
    assert "localhost" in config.OLLAMA_BASE_URL
    assert hasattr(config, "has_live_key")


def test_lookup_known_order():
    row = lookup_order("Can I return order NS-1001?")
    assert row["found"] is True
    assert row["item"] == "desk lamp"
    assert row["days_since_delivery"] == 12


def test_lookup_unknown_order():
    row = lookup_order("Can I return order NS-9999?")
    assert row["found"] is False


def test_policy_names_thirty_days():
    page = read_policy("return")
    assert "30 days" in page["text"]


def test_escalate_sets_the_gate():
    out = escalate_to_human("this is not in the policy")
    assert out["escalate"] is True
    assert out["queue"] == "support-human"


def test_fixture_loop_stops():
    tools = {
        "orders": lookup_order,
        "policy": read_policy,
        "escalate": escalate_to_human,
    }
    out = run_loop("Can I return order NS-1001?", tools)
    actions = [step["action"] for step in out["steps"]]
    assert "orders" in actions
    assert actions[-1] == "stop"


def test_health_does_not_need_fastapi():
    assert health()["ok"] is True
