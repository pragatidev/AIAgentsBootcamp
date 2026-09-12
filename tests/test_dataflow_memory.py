"""6.4 DataFlow checkpointer and store. Pytest stays green with no live model."""

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.memory import InMemoryStore

from dataflow.graphs.v1_triage import DeskContext
from dataflow.graphs.v3_memory import (
    PREFERENCE_KEY,
    build_v3_memory,
    preference_namespace,
)
from tests.fixtures.fake_model import FakeChatModel


def _human_texts(state: dict) -> list[str]:
    texts: list[str] = []
    for message in state.get("messages") or []:
        if getattr(message, "type", "") == "human":
            texts.append(str(getattr(message, "content", "")))
    return texts


def _count(graph, config) -> int:
    return len(list(graph.get_state_history(config)))


def test_second_invoke_continues():
    model = FakeChatModel(route="orders", reply="looked up desk lamp")
    graph = build_v3_memory(model=model)
    cfg = {"configurable": {"thread_id": "test-10-2"}}
    context = DeskContext(customer_id="C-2001")
    first = graph.invoke(
        {
            "ticket": "Hi, I want to return order DF-1001. The desk lamp is unused.",
            "messages": [
                HumanMessage(
                    content="Hi, I want to return order DF-1001. The desk lamp is unused."
                )
            ],
        },
        cfg,
        context=context,
    )
    n1 = _count(graph, cfg)
    second = graph.invoke(
        {
            "ticket": "Quick one: can I add a warranty to DF-1001 after delivery?",
            "messages": [
                HumanMessage(
                    content="Quick one: can I add a warranty to DF-1001 after delivery?"
                )
            ],
        },
        cfg,
        context=context,
    )
    n2 = _count(graph, cfg)
    assert n1 > 0
    assert n2 > n1
    humans = _human_texts(second)
    assert any("desk lamp" in text.lower() for text in humans)
    assert any("warranty" in text.lower() for text in humans)
    assert first.get("reply")
    assert second.get("reply")
    assert second.get("turns") == 2


def test_resume_after_restart(tmp_path):
    db = tmp_path / "checkpoints.sqlite"
    model = FakeChatModel(route="orders", reply="looked up desk lamp")
    cfg = {"configurable": {"thread_id": "test-10-3"}}
    context = DeskContext(customer_id="C-2001")
    turn_one = "Hi, I want to return order DF-1001. The desk lamp is unused."
    turn_two = "Quick one: can I add a warranty to DF-1001 after delivery?"

    with SqliteSaver.from_conn_string(str(db)) as saver:
        saver.setup()
        graph = build_v3_memory(checkpointer=saver, model=model)
        graph.invoke(
            {"ticket": turn_one, "messages": [HumanMessage(content=turn_one)]},
            cfg,
            context=context,
        )

    with SqliteSaver.from_conn_string(str(db)) as saver2:
        saver2.setup()
        graph2 = build_v3_memory(checkpointer=saver2, model=model)
        saved = graph2.get_state(cfg)
        assert saved.values.get("reply")
        assert "DF-1001" in " ".join(_human_texts(saved.values))
        second = graph2.invoke(
            {"ticket": turn_two, "messages": [HumanMessage(content=turn_two)]},
            cfg,
            context=context,
        )
        humans = _human_texts(second)
        assert any("desk lamp" in text.lower() for text in humans)
        assert any("warranty" in text.lower() for text in humans)
        assert second.get("turns") == 2


def test_store_survives_new_thread():
    store = InMemoryStore()
    model = FakeChatModel(route="policy", reply="noted")
    graph = build_v3_memory(store=store, model=model)
    customer = "C-2001"
    pref_text = "please always email me, never call"
    graph.invoke(
        {"ticket": pref_text, "messages": [HumanMessage(content=pref_text)]},
        {"configurable": {"thread_id": "thread-a"}},
        context=DeskContext(customer_id=customer),
    )
    item = store.get(preference_namespace(customer), PREFERENCE_KEY)
    assert item is not None
    assert item.value.get("channel") == "email"

    follow = "Where is order DF-1001?"
    second = graph.invoke(
        {"ticket": follow, "messages": [HumanMessage(content=follow)]},
        {"configurable": {"thread_id": "thread-b"}},
        context=DeskContext(customer_id=customer),
    )
    pref = second.get("preference") or {}
    assert pref.get("channel") == "email"
    assert second.get("reply")


def test_new_customer_has_no_preference():
    store = InMemoryStore()
    model = FakeChatModel(route="policy", reply="noted")
    graph = build_v3_memory(store=store, model=model)
    pref_text = "please always email me, never call"
    graph.invoke(
        {"ticket": pref_text, "messages": [HumanMessage(content=pref_text)]},
        {"configurable": {"thread_id": "thread-known"}},
        context=DeskContext(customer_id="C-2001"),
    )
    other = "What is your return window?"
    miss = graph.invoke(
        {"ticket": other, "messages": [HumanMessage(content=other)]},
        {"configurable": {"thread_id": "thread-other"}},
        context=DeskContext(customer_id="C-2099"),
    )
    assert miss.get("preference") in (None, {})
    assert store.get(preference_namespace("C-2099"), PREFERENCE_KEY) is None
