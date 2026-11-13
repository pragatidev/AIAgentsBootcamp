"""Lab 13_03_07 (Lecture 29.7), check_server typed by the student: an allowlist with pinned fingerprints.

The servers run in process; no model is called and the registry cell stays off (it needs the network).
"""

import runpy
from pathlib import Path

import pytest

from dataflow.mcp.allowlist import ALLOWLIST_PATH, check_server as package_check, load_allowlist
from dataflow.mcp.bind import bind_mcp_tools, close_mcp
from dataflow.mcp.fixtures.weather_server import weather
from dataflow.mcp.kb_server import kb
from dataflow.mcp.server import mcp as orders
from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_03_07_server_allowlist.py"
TOOL_LOOP = (
    "    for tool in tools:\n"
    "        pinned = entry[\"tools\"].get(tool.name)\n"
    "        if pinned is None:\n"
    "            refusals.append(f\"{name}.{tool.name} was never approved\")\n"
    "        elif pinned != fingerprint(tool):\n"
    "            refusals.append(f\"{name}.{tool.name} changed since it was approved\")\n"
)


@pytest.fixture
def run_lab(monkeypatch, capsys):
    monkeypatch.delenv("DATAFLOW_REGISTRY_LOOKUP", raising=False)

    def run(path: Path = LAB):
        lab = runpy.run_path(str(path), run_name="__main__")
        return lab, capsys.readouterr().out.splitlines()

    return run


@pytest.fixture
def servers():
    bound = {"dataflow": bind_mcp_tools(orders), "kb": bind_mcp_tools(kb), "third-party-weather": bind_mcp_tools(weather)}
    yield bound
    close_mcp()


def test_the_committed_allowlist_pins_the_servers_as_they_are(servers):
    allowlist = load_allowlist()
    assert set(allowlist["servers"]) == {"dataflow", "kb"}
    assert package_check("dataflow", servers["dataflow"], allowlist) == []
    assert package_check("kb", servers["kb"], allowlist) == []


def test_approved_servers_load_and_the_unlisted_one_is_refused(run_lab):
    _, out = run_lab()
    assert "server dataflow loads []" in out and "server kb loads []" in out
    assert "server third-party-weather refused ['server third-party-weather is not on the allowlist']" in out
    assert "desk_tools ['lookup_order', 'refund', 'retrieve']" in out


def test_a_changed_description_is_refused_until_approved(run_lab):
    _, out = run_lab()
    pinned = next(line for line in out if line.startswith("pinned_fingerprint ")).split()[1]
    new = next(line for line in out if line.startswith("new_fingerprint ")).split()[1]
    assert pinned != new and len(pinned) == len(new) == 16
    assert "server dataflow refused ['dataflow.lookup_order changed since it was approved']" in out
    assert "after_update refused" in out and "after_approval loads" in out
    assert "allowlist_json_unchanged True" in out
    assert "registry_lookup skipped (set DATAFLOW_REGISTRY_LOOKUP=1 to run it; it needs the network)" in out


def test_lab_check_matches_the_package(run_lab, servers):
    lab, _ = run_lab()
    allowlist = load_allowlist()
    for name, tools in servers.items():
        assert lab["check_server"](name, tools, allowlist) == package_check(name, tools, allowlist), name
    assert lab["check_server"]("dataflow", servers["kb"], allowlist) == ["dataflow.retrieve was never approved"]


def test_checking_names_only_lets_the_changed_description_load(run_lab, tmp_path):
    before = ALLOWLIST_PATH.read_text(encoding="utf-8")
    copy = lab_copy(LAB, tmp_path, TOOL_LOOP, "")
    _, out = run_lab(copy)
    assert "server third-party-weather refused ['server third-party-weather is not on the allowlist']" in out
    assert "after_update loads" in out
    assert ALLOWLIST_PATH.read_text(encoding="utf-8") == before
