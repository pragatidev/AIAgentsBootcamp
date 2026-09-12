"""TechCorp account tools. One happy path, one miss. No model."""

from types import SimpleNamespace

from techcorp.tools.accounts import (
    dummy_runtime,
    grant_access,
    lookup_user,
    reload_users,
    reset_password,
)


def test_unknown_user_is_a_miss():
    out = reset_password.func("E-0000", runtime=dummy_runtime())
    assert out["found"] is False
    assert "temporary_password" not in out
    assert out["reason"] == "unknown user E-0000"


def test_known_user_resets():
    out = reset_password.func("E-4101", runtime=dummy_runtime())
    assert out["found"] is True
    assert out["user_id"] == "E-4101"
    assert out["expires_in_hours"] == 24
    assert isinstance(out["temporary_password"], str)
    assert len(out["temporary_password"]) == 10


def test_lookup_by_name():
    hit = lookup_user.invoke({"query": "amina cole"})
    assert hit["found"] is True
    assert hit["user_id"] == "E-4101"
    assert hit["name"] == "Amina Cole"
    miss = lookup_user.invoke({"query": "nobody here"})
    assert miss["found"] is False
    assert miss["reason"] == "unknown user nobody here"


def test_grant_access_appends():
    reload_users()
    out = grant_access.invoke({"user_id": "E-4104", "share": "finance-q3"})
    assert out["found"] is True
    assert "finance-q3" in out["groups"]
    again = grant_access.invoke({"user_id": "E-4104", "share": "finance-q3"})
    assert again["groups"].count("finance-q3") == 1
    miss = grant_access.invoke({"user_id": "E-0000", "share": "finance-q3"})
    assert miss["found"] is False
    assert miss["reason"] == "unknown user E-0000"
    reload_users()


def test_context_id_wins():
    runtime = SimpleNamespace(context=SimpleNamespace(user_id="E-4101"))
    out = reset_password.func("E-4102", runtime=runtime)
    assert out["found"] is True
    assert out["user_id"] == "E-4101"
    assert out["user_id"] != "E-4102"
