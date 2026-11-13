"""Lab 13_01_01 (Lecture 28.3), envelope typed by the student: four raw JSON-RPC lines to the repo's own server over stdio."""

import json
import runpy
from pathlib import Path

from dataflow.mcp.server import PID_PATH
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_01_01_mcp_by_hand.py"
VERSION_LINE = '        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,\n'
CAPABILITIES_LINE = '        "io.modelcontextprotocol/clientCapabilities": {},\n'


def _run(path: Path, capsys) -> tuple[dict, list[str]]:
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_envelope_carries_both_meta_keys(capsys):
    lab, _ = _run(LAB, capsys)
    message = json.loads(lab["envelope"]("tools/list", {}, 7))
    assert message == {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/list",
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
            }
        },
    }


def test_the_server_answers_discover_list_and_call(capsys):
    _, out = _run(LAB, capsys)
    assert "discover supportedVersions ['2026-07-28']" in out
    assert "discover serverInfo {'name': 'dataflow', 'version': '4.0.3'}" in out
    assert "tools_first ['lookup_order', 'refund']" in out
    assert "tools_second ['lookup_order', 'refund']" in out
    assert "tools_same_order True" in out
    assert 'lookup_order annotations {"readOnlyHint": true}' in out
    assert "call structuredContent found True" in out
    assert "call isError False" in out
    assert "server_exit_code 0" in out
    assert "pid_file_left False" in out
    assert not PID_PATH.is_file()


def test_without_the_version_key_the_server_reads_an_older_client(capsys, tmp_path):
    copy = lab_copy(LAB, tmp_path, VERSION_LINE, "")
    _, out = _run(copy, capsys)
    assert "server/discover error -32601 Method not found" in out
    assert out.count("tools/list error -32602 Invalid request parameters") == 2
    assert "tools/call error -32602 Invalid request parameters" in out
    assert not any(line.startswith("discover supportedVersions") for line in out)
    assert "server_exit_code 0" in out


def test_without_the_capabilities_key_each_answer_names_it(capsys, tmp_path):
    copy = lab_copy(LAB, tmp_path, CAPABILITIES_LINE, "")
    _, out = _run(copy, capsys)
    refused = [line for line in out if " error -32602 " in line]
    assert len(refused) == 4, out
    assert all(line.endswith("missing the required envelope key(s): io.modelcontextprotocol/clientCapabilities") for line in refused)
    assert "server_exit_code 0" in out
