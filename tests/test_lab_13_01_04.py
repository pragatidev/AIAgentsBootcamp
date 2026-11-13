"""Lab 13_01_04 (Lecture 28.7), call_lookup typed by the student: a FastMCP Client starts the server over stdio from a config."""

import runpy
from pathlib import Path

from dataflow.mcp.client import RUNS_PATH
from dataflow.mcp.server import PID_PATH
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_01_04_mcp_client.py"
ENV_LINE = 'server["env"] = stdio_env()\n'


def _run(path: Path, capfd) -> tuple[list[str], str]:
    runpy.run_path(str(path), run_name="__main__")
    captured = capfd.readouterr()
    return captured.out.splitlines(), captured.err


def test_the_client_starts_the_server_and_looks_up_df_1001(capfd):
    committed = RUNS_PATH.read_text(encoding="utf-8")
    out, _ = _run(LAB, capfd)
    assert "config_command_was python -m dataflow.mcp.server" in out
    assert any(line.startswith("config_command_now ") and line.endswith(" -m dataflow.mcp.server") and "python" in line for line in out)
    assert "protocol_version 2026-07-28" in out
    assert "tools ['lookup_order', 'refund']" in out
    assert any(line.startswith("result {'found': True, 'order_id': 'DF-1001'") for line in out)
    assert "server_stopped True" in out
    assert "restored_client True" in out and "pid_file_left False" in out
    assert RUNS_PATH.read_text(encoding="utf-8") == committed
    assert not PID_PATH.is_file()


def test_the_committed_runs_file_matches_what_the_lab_writes(capfd):
    import json

    committed = json.loads(RUNS_PATH.read_text(encoding="utf-8"))
    assert committed["transport"] == "stdio"
    assert committed["protocol_version"] == "2026-07-28"
    assert committed["tools"] == ["lookup_order", "refund"]
    assert committed["result"]["found"] is True


def test_without_env_the_child_cannot_import_dataflow_and_fails_fast(capfd, tmp_path):
    copy = lab_copy(LAB, tmp_path, ENV_LINE, "")
    out, err = _run(copy, capfd)
    assert "child_env_keys []" in out
    assert "client_error MCPError Connection closed" in out
    seconds = float(next(line for line in out if line.startswith("seconds ")).split()[1])
    assert seconds < 10
    assert "No module named 'dataflow'" in err
    assert not any(line.startswith("protocol_version") for line in out)
    assert "pid_file_left False" in out
