"""Lab 06.04.05 (13.3), owner, read_pref_node and write_pref_node typed by the student. The fixture model's
PreferenceDecision says email when the ticket says email, else none."""

import runpy
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage
from langgraph.store.memory import InMemoryStore

import config
from dataflow.envelope import DeskContext
from dataflow.graphs.v3_memory import PREFERENCE_KEY, build_v3_memory, preference_namespace
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_04_05_store_facts.py"
OWNER = '    return ("customers", runtime.context.customer_id)\n'
BY_THREAD = '    return ("customers", get_config()["configurable"]["thread_id"])\n'
EMAIL = {"channel": "email", "stated": True}
TICKETS = [
    ("t-a", "C-2001", "please always email me, never call"),
    ("t-b", "C-2001", "Where is order DF-1001?"),
    ("t-c", "C-2099", "What is your return window?"),
]


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="orders", reply="We will email you."))


def test_lab_hit_on_b_miss_on_c(scripted, capsys):
    runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    a, b, c = (out.index(f"thread lab-13-3-{x} customer {cust} ticket {t}") for x, (_, cust, t) in zip("abc", TICKETS))
    assert out[a + 1 : a + 4] == [
        "   read_pref {'preference': None}",
        f"   write_pref {{'preference': {EMAIL}}}",
        f"   store ('customers', 'C-2001') preferences {EMAIL}",
    ]
    assert out[b + 1] == f"   read_pref {{'preference': {EMAIL}}}"
    assert out[b + 2] == "   write_pref None"
    assert out[c + 1] == "   read_pref {'preference': None}"
    assert f"desk preference {EMAIL}" in out
    assert out[-2:] == ["search_default 10 of 12", "search_limit_20 12 of 12"]


def test_typed_nodes_match_the_package(scripted):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    mine_store, package_store = InMemoryStore(), InMemoryStore()
    mine = lab["build_store_desk"](mine_store)
    package = build_v3_memory(store=package_store, model=FakeChatModel(route="orders", reply="ok"))
    for thread_id, customer, ticket in TICKETS:
        cfg = {"configurable": {"thread_id": thread_id}}
        got = mine.invoke({"ticket": ticket}, cfg, context=DeskContext(customer_id=customer, model=FakeChatModel()))
        want = package.invoke({"ticket": ticket, "messages": [HumanMessage(content=ticket)]}, cfg,
                              context=DeskContext(customer_id=customer))
        assert got.get("preference") == want.get("preference")
    for customer in ("C-2001", "C-2099"):
        mine_item = mine_store.get(preference_namespace(customer), PREFERENCE_KEY)
        package_item = package_store.get(preference_namespace(customer), PREFERENCE_KEY)
        assert (mine_item and mine_item.value) == (package_item and package_item.value)


def test_break_namespace_by_thread_misses_on_b(scripted, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, OWNER, BY_THREAD)
    runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    b = out.index(f"thread lab-13-3-b customer C-2001 ticket {TICKETS[1][2]}")
    assert out[b + 1] == "   read_pref {'preference': None}"
    assert f"   store ('customers', 'lab-13-3-a') preferences {EMAIL}" in out
    assert not any(line.startswith("   store ('customers', 'C-2001')") for line in out)
