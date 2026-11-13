"""Lab 13_03_02 (Lecture 29.2), serve_http and mcp_headers typed by the student: the orders server over Streamable HTTP.

No model is called. The server runs on a free local port in a thread of the test process.
"""

import json
import runpy
from pathlib import Path

import pytest

from dataflow.mcp.http import mcp_headers as package_headers
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_03_02_serve_http.py"
NAME_LINE = '        headers["Mcp-Name"] = body["params"]["name"]\n'


@pytest.fixture
def run_lab(monkeypatch, capsys):
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", "")

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    return run


def _rows(lab) -> list[dict]:
    text = Path(lab["ledger"].name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_a_real_client_negotiates_2026_07_28_over_http(run_lab):
    _, out = run_lab()
    assert "protocol_version 2026-07-28" in out
    assert "tools ['lookup_order', 'refund']" in out
    assert any(line.startswith("url http://127.0.0.1:") and line.endswith("/mcp") for line in out)


def test_requests_by_hand_carry_mirrored_headers_and_no_session(run_lab):
    lab, out = run_lab()
    assert out.count("  session_id_header False") == 3
    assert out.count("  status 200") == 3
    assert "  sent Mcp-Name lookup_order" in out and "  sent Mcp-Name refund" in out
    assert "  supportedVersions ['2026-07-28']" in out
    assert '"order_id": "DF-1001", "item": "desk lamp"' in next(line for line in out if line.startswith("  structuredContent"))
    assert "ledger_rows 1" in out and len(_rows(lab)) == 1
    assert "server_stopped True" in out


def test_lab_headers_match_the_package(run_lab):
    lab, _ = run_lab()
    body = lab["envelope"]("tools/call", {"name": "refund", "arguments": {}}, 9)
    assert lab["mcp_headers"](body) == package_headers(body)
    body = lab["envelope"]("tools/list", None, 10)
    assert lab["mcp_headers"](body) == package_headers(body)


def test_a_header_that_lies_about_the_body_is_refused(run_lab, tmp_path):
    copy = lab_copy(LAB, tmp_path, NAME_LINE, '        headers["Mcp-Name"] = "lookup_order"\n')
    lab, out = run_lab(copy)
    at = out.index("request tools/call refund")
    refused = out[at:]
    assert "  sent Mcp-Name lookup_order" in refused
    assert "  status 400" in refused
    assert "  error -32020 mcp-name header does not match the request body's 'name' parameter" in refused
    assert "ledger_rows 0" in out and _rows(lab) == []
