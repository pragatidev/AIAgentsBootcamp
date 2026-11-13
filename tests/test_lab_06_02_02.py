"""Lab 06.02.02 (11.2), route_after_classify and build_route typed by the student. A scripted classifier stands in
for the real model here, and only here."""

import runpy
from pathlib import Path

import pytest

import config
from dataflow.graphs.v2_route import build_v2_route, pick_route
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_02_02_route_three_ways.py"
ROUTES = {"Where is order DF-1001?": "orders", "What is your return window?": "policy", "I want a manager now.": "escalate"}


@pytest.fixture
def lab(monkeypatch, capsys):
    model = FakeChatModel(structured={"RouteDecision": [{"route": "orders"}, {"route": "policy"}, {"route": "escalate"}]})
    monkeypatch.setattr(config, "get_chat_model", lambda **k: model)
    globals_ = runpy.run_path(str(LAB), run_name="__main__")
    globals_["_out"] = capsys.readouterr().out.splitlines()
    return globals_


def test_three_tickets_three_roads(lab):
    out = lab["_out"]
    for label in ("orders", "policy", "escalate"):
        assert f"\tclassify -. &nbsp;{label}&nbsp; .-> {label}_desk;" in out
    assert [line.split()[1] for line in out if line.startswith("ticket ")] == ["T-3002", "T-3003", "T-3027"]
    assert [line for line in out if line.startswith("route ")] == ["route orders", "route policy", "route escalate"]
    assert [line.split()[1:4] for line in out if line.startswith("desk ")] == [
        ["orders_desk", "wrote", "order"],
        ["policy_desk", "wrote", "policy"],
        ["escalate_desk", "wrote", "escalation"],
    ]
    assert "reply Order DF-1002 is in_transit. Item: USB-C hub." in out


def test_router_matches_the_package_and_has_a_safe_default(lab):
    router = lab["route_after_classify"]
    for label in ("orders", "policy", "escalate", "billing", "", None):
        assert router({"route": label}) == pick_route({"route": label})
    assert router({"route": "billing"}) == "escalate"
    assert router({}) == "escalate"


def test_typed_graph_routes_like_the_package(lab):
    for ticket, route in ROUTES.items():
        mine = lab["build_route"](model=FakeChatModel(route=route)).invoke({"ticket": ticket})
        package = build_v2_route(model=FakeChatModel(route=route)).invoke({"ticket": ticket})
        assert mine == package
        assert mine["route"] == route
    mine = lab["build_route"](model=FakeChatModel(route="orders"))
    package = build_v2_route(model=FakeChatModel(route="orders"))
    assert set(mine.get_graph().nodes) == set(package.get_graph().nodes)
    assert {(e.source, e.target, e.conditional) for e in mine.get_graph().edges} == {
        (e.source, e.target, e.conditional) for e in package.get_graph().edges
    }


def test_break_unmapped_label_raises_key_error(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="orders"))
    broken = lab_copy_dataflow(LAB, tmp_path, "        return route\n", '        return "billing"\n')
    with pytest.raises(KeyError, match="billing"):
        runpy.run_path(str(broken), run_name="__main__")
