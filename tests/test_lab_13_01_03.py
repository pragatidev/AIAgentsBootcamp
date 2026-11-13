"""Lab 13_01_03 (Lecture 28.5), lookup_order typed by the student on a lab FastMCP server, called in process."""

import runpy
from pathlib import Path

from dataflow.mcp.server import call_tool
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_01_03_fastmcp_server.py"
GUARD = '    if table not in TABLES:\n        return {"found": False, "reason": "unknown table"}\n'


def _run(path: Path, capsys) -> tuple[dict, list[str]]:
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_schema_and_annotation_come_from_the_function(capsys):
    _, out = _run(LAB, capsys)
    text = "\n".join(out)
    assert '"order_id": {\n      "type": "string"\n    }' in text
    assert '"table": {\n      "default": "orders",\n      "type": "string"\n    }' in text
    assert "description Look up a DataFlow order by id like DF-1001. table must be orders." in out
    assert "annotations read_only_hint True" in out


def test_df_1001_is_found_and_an_unknown_table_is_a_miss(capsys):
    _, out = _run(LAB, capsys)
    assert any(line.startswith("DF-1001 structured_content {'found': True, 'order_id': 'DF-1001', 'item': 'desk lamp'") for line in out)
    assert "table customers {'found': False, 'reason': 'unknown table'}" in out


def test_the_lab_tool_answers_as_the_package_tool(capsys):
    lab, _ = _run(LAB, capsys)
    for args in ({"order_id": "DF-1001"}, {"order_id": "DF-1001", "table": "customers"}, {"order_id": "DF-9999"}):
        assert lab["lookup_order"](**args) == call_tool("lookup_order", args)


def test_without_the_guard_the_customers_call_is_accepted(capsys, tmp_path):
    copy = lab_copy(LAB, tmp_path, GUARD, "")
    _, out = _run(copy, capsys)
    customers = next(line for line in out if line.startswith("table customers "))
    assert "unknown table" not in customers
    assert customers.startswith("table customers {'found': True, 'order_id': 'DF-1001'")
