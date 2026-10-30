"""TechCorp account tools. One happy path, one miss. No model."""

import json
from types import SimpleNamespace

import pytest

from techcorp.tools import accounts as accounts_mod
from techcorp.tools.accounts import (
    dummy_runtime,
    grant_access,
    lookup_user,
    reload_users,
    reset_password,
)


@pytest.fixture(autouse=True)
def audit_path(tmp_path, monkeypatch):
    # Every test here writes its audit lines to a temporary file, never to techcorp/data/audit.jsonl.
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(accounts_mod, "AUDIT_PATH", path)
    return path


def test_unknown_user_is_a_miss():
    out = reset_password.func("E-0000", runtime=dummy_runtime("E-0000"))
    assert out["found"] is False
    assert "temporary_password" not in out
    assert out["reason"] == "unknown user E-0000"


def test_known_user_resets():
    out = reset_password.func("E-4101", runtime=dummy_runtime("E-4101"))
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


def test_grant_access_appends(audit_path):
    reload_users()
    out = grant_access.func("E-4104", "finance-q3", runtime=dummy_runtime("E-4106"))
    assert out["found"] is True
    assert "finance-q3" in out["groups"]
    again = grant_access.func("E-4104", "finance-q3", runtime=dummy_runtime("E-4106"))
    assert again["groups"].count("finance-q3") == 1
    assert json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])["by"] == "E-4106"
    miss = grant_access.func("E-0000", "finance-q3", runtime=dummy_runtime("E-4106"))
    assert miss["found"] is False
    assert miss["reason"] == "unknown user E-0000"
    reload_users()


def test_context_id_wins():
    runtime = SimpleNamespace(context=SimpleNamespace(user_id="E-4101"))
    out = reset_password.func("E-4102", runtime=runtime)
    assert out["found"] is True
    assert out["user_id"] == "E-4101"
    assert out["user_id"] != "E-4102"


def test_audit_line_has_no_secret(audit_path):
    out = reset_password.func("E-4101", runtime=dummy_runtime("E-4101"))
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["action"] == "reset_password" and row["user_id"] == "E-4101"
    assert "temporary_password" not in row
    assert out["temporary_password"] not in lines[0]


def test_temporary_password_is_not_derivable():
    first = reset_password.func("E-4101", runtime=dummy_runtime("E-4101"))
    second = reset_password.func("E-4101", runtime=dummy_runtime("E-4101"))
    assert first["temporary_password"] != second["temporary_password"]
    # The old formula: the first 10 hex of sha256("E-4101:1"). Anyone who knew the id knew it.
    assert first["temporary_password"] != "581cd31c70"


@pytest.mark.parametrize(
    "acting, expected",
    [
        ("E-0000", {"found": False, "reason": "unknown user E-0000"}),
        ("", {"found": False, "reason": "no user id"}),
    ],
)
def test_typed_miss_both_paths(acting, expected):
    assert accounts_mod.reset_outcome(acting) == expected
    hit = accounts_mod.reset_outcome("E-4101")
    assert hit["found"] is True and hit["user_id"] == "E-4101"
    assert len(hit["temporary_password"]) == 10 and hit["expires_in_hours"] == 24


def test_empty_envelope_is_a_typed_miss(audit_path):
    out = reset_password.func("E-4101", runtime=dummy_runtime())
    assert out == {"found": False, "reason": "no acting user in the request envelope"}
    assert not audit_path.exists()


def test_mismatch_is_marked_in_the_audit(audit_path):
    out = reset_password.func("E-4102", runtime=dummy_runtime("E-4101"))
    assert out["user_id"] == "E-4101"
    assert out["requested_user_id_ignored"] == "E-4102"
    row = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert row["user_id"] == "E-4101" and row["requested_user_id"] == "E-4102"
    assert row["mismatch"] is True
