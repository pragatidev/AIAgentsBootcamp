"""Part 4 profile and recall. Fixture embedder. No Ollama."""

from datetime import datetime, timedelta, timezone

from langgraph.store.memory import InMemoryStore

from dataflow.memory.profile import forget, put_profile, read_profile
from dataflow.memory.recall import build_recall_store, file_note, recall
from tests.fixtures.fake_embedder import FakeEmbedder


def test_stale_key_dropped():
    store = InMemoryStore()
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    put_profile(
        store,
        "C-2001",
        "contact_channel",
        "email",
        source="stated",
        written_at=now,
    )
    put_profile(
        store,
        "C-2001",
        "mood",
        "angry last Tuesday",
        source="stated",
        written_at=now - timedelta(days=8),
    )
    out = read_profile(store, "C-2001", now=now)
    assert "contact_channel" in out["profile"]
    assert "mood" in out["dropped"]
    assert "mood" not in out["profile"]


def test_forget_empties_namespace():
    store = InMemoryStore()
    put_profile(store, "C-2001", "contact_channel", "email", source="stated")
    deleted = forget(store, "C-2001")
    assert "profile" in deleted
    out = read_profile(store, "C-2001")
    assert out["profile"] == {}


def test_other_customer_reads_nothing():
    store = InMemoryStore()
    put_profile(store, "C-2001", "contact_channel", "email", source="stated")
    other = read_profile(store, "C-2099")
    assert other["profile"] == {}
    assert other["dropped"] == []


def test_recall_stays_in_namespace():
    embedder = FakeEmbedder()
    store = build_recall_store(embedder=embedder, dims=768)
    file_note(store, "C-2001", "csv_upload", "Dashboard breaks on large csv upload")
    file_note(store, "C-2099", "csv_upload", "Dashboard breaks on large csv upload")
    hits = recall(store, "C-2001", "upload page is slow for a big csv", floor=0.0)
    assert hits
    assert all(item["namespace"] == ("customers", "C-2001") for item in hits)
    assert all(item["namespace"][1] != "C-2099" for item in hits)
