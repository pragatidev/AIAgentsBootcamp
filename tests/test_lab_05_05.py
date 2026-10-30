"""Lab 05.05, lookup_user typed by the student. No model anywhere."""

import runpy
from pathlib import Path

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from techcorp.tools import accounts

LAB = Path(__file__).resolve().parents[1] / "labs" / "05_05_write_a_typed_tool.py"
DOCSTRING = '    """Look up a TechCorp employee by user id (E-4101) or by name. Returns the record or a typed miss. Use this before you reset a password."""\n'


@pytest.fixture
def lab(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(accounts, "AUDIT_PATH", tmp_path / "audit.jsonl")
    globals_ = runpy.run_path(str(LAB), run_name="__main__")
    globals_["_out"] = capsys.readouterr().out.splitlines()
    return globals_


def _copy_with(tmp_path, old: str, new: str) -> Path:
    text = LAB.read_text(encoding="utf-8")
    assert text.count(old) == 1
    copy = tmp_path / "labs" / LAB.name
    copy.parent.mkdir(exist_ok=True)
    copy.write_text(text.replace(old, new), encoding="utf-8")
    return copy


@pytest.mark.parametrize("query", ["E-4101", "amina cole", "E-0000", ""])
def test_typed_lookup_matches_shipped(lab, query):
    assert lab["lookup_user"].invoke({"query": query}) == accounts.lookup_user.invoke({"query": query})


def test_typed_lookup_schema_matches_shipped(lab):
    assert convert_to_openai_tool(lab["lookup_user"]) == convert_to_openai_tool(accounts.lookup_user)


def test_runtime_is_hidden_from_the_model(lab):
    params = convert_to_openai_tool(accounts.reset_password)["function"]["parameters"]
    assert list(params["properties"]) == ["user_id"]
    assert 'handed_to_the_model {"properties": {"user_id": {"type": "string"}}, "required": ["user_id"], "type": "object"}' in lab["_out"]


def test_lab_prints_the_hit_and_the_miss(lab):
    out = lab["_out"]
    assert any(line.startswith("hit {'found': True, 'user_id': 'E-4101', 'name': 'Amina Cole'") for line in out)
    assert "miss {'found': False, 'reason': 'unknown user E-0000'}" in out


def test_tool_without_docstring_is_refused(tmp_path):
    copy = _copy_with(tmp_path, DOCSTRING, "")
    with pytest.raises(ValueError, match="must have a docstring"):
        runpy.run_path(str(copy), run_name="__main__")


def test_wrong_field_name_is_refused(tmp_path):
    copy = _copy_with(tmp_path, 'lookup_user.invoke({"query": "E-4101"})', 'lookup_user.invoke({"user": "E-4101"})')
    with pytest.raises(ValidationError, match="query"):
        runpy.run_path(str(copy), run_name="__main__")
