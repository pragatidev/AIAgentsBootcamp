"""6.6 DataFlow streaming and time travel. Pytest stays green with no live model."""

from dataflow.graphs.v3_memory import build_v3_memory
from dataflow.graphs.v5_stream import build_v5_stream
from tests.fixtures.fake_model import FakeChatModel

TICKET = "Hi, I want to return order DF-1001. The desk lamp is unused. Can I get a refund?"
EDITED = "The return window is 30 days and the lamp qualifies."


def _thread(name: str) -> dict:
    return {"configurable": {"thread_id": name}}


def _part_type(part) -> str | None:
    if isinstance(part, dict) and "type" in part:
        return str(part["type"])
    return None


def _part_data(part):
    if isinstance(part, dict) and "data" in part:
        return part["data"]
    return part


def _update_nodes(parts) -> set[str]:
    names: set[str] = set()
    for part in parts:
        if _part_type(part) not in (None, "updates"):
            continue
        data = _part_data(part)
        if not isinstance(data, dict):
            continue
        for name in data:
            if not str(name).startswith("__"):
                names.add(str(name))
    return names


def test_stream_yields_both_lanes():
    model = FakeChatModel(route="orders", reply="looked up desk lamp")
    graph = build_v5_stream(model=model)
    parts = list(
        graph.stream(
            {"ticket": TICKET},
            _thread("test-12-both"),
            stream_mode=["updates", "messages"],
            version="v2",
        )
    )
    types = {_part_type(part) for part in parts}
    assert "updates" in types
    assert "messages" in types


def test_updates_names_every_node():
    model = FakeChatModel(route="orders", reply="looked up desk lamp")
    graph = build_v5_stream(model=model)
    cfg = _thread("test-12-nodes")
    parts = list(
        graph.stream(
            {"ticket": TICKET},
            cfg,
            stream_mode="updates",
            version="v2",
        )
    )
    ran = _update_nodes(parts)
    assert ran == {
        "ingest",
        "read_pref",
        "classify",
        "orders_desk",
        "write_pref",
        "speak",
    }


def test_custom_lane_emits():
    model = FakeChatModel(route="orders", reply="looked up desk lamp")
    graph = build_v5_stream(model=model)
    parts = list(
        graph.stream(
            {"ticket": TICKET},
            _thread("test-12-custom"),
            stream_mode=["custom"],
            version="v2",
        )
    )
    progress = []
    for part in parts:
        if _part_type(part) not in (None, "custom"):
            continue
        data = _part_data(part)
        if isinstance(data, dict) and "progress" in data:
            progress.append(data)
    assert len(progress) >= 1


def test_fork_keeps_original_history():
    model = FakeChatModel(route="orders", reply="looked up desk lamp")
    graph = build_v3_memory(model=model)
    cfg = _thread("test-12-fork-history")
    graph.invoke({"ticket": TICKET}, cfg)
    history = list(graph.get_state_history(cfg))
    n_before = len(history)
    before_speak = next(
        snap for snap in history if tuple(snap.next) == ("speak",)
    )
    original_id = before_speak.config["configurable"]["checkpoint_id"]
    fork_config = graph.update_state(
        before_speak.config,
        values={"reply": EDITED},
    )
    graph.invoke(None, fork_config)
    history_after = list(graph.get_state_history(cfg))
    assert len(history_after) > n_before
    ids = {
        snap.config["configurable"]["checkpoint_id"] for snap in history_after
    }
    assert original_id in ids


def test_fork_reruns_nodes_after_the_fork_point():
    model = FakeChatModel(route="orders", reply="looked up desk lamp")
    graph = build_v3_memory(model=model)
    cfg = _thread("test-12-fork-rerun")
    first = graph.invoke({"ticket": TICKET}, cfg)
    calls_before = model.calls
    history = list(graph.get_state_history(cfg))
    before_speak = next(
        snap for snap in history if tuple(snap.next) == ("speak",)
    )
    fork_config = graph.update_state(
        before_speak.config,
        values={"reply": EDITED},
    )
    forked = graph.invoke(None, fork_config)
    assert model.calls > calls_before
    assert first.get("reply")
    assert forked.get("reply")
