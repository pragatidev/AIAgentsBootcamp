"""Lab 06.10.02 (18.2): the served graph ids, the dev-server helper and the client typed by the student. No langgraph
dev runs here: the live run through the real server is a capture (the course venv's langgraph-api 0.14.0 does not start
on its protobuf, and a test must not need a port of its own for minutes).

The helper is tested against a stand-in server: it prints the lines langgraph dev prints (the API and Studio URLs, a
langgraph-api version), then starts a child process that holds the port and answers GET /ok, the way a server with a
worker under it does. The helper must find it ready, read the URLs and the version, and leave nothing behind: the child
gone and the port free.

The lab and its break are run against a recording client that keeps the SDK's shapes as the real server returned them
on langgraph-api 0.10.3 (LG-R6's probe and captures): a thread id, update parts, a state with next as a list and tasks
with interrupts, the final values from wait, the 422 UnprocessableEntityError for a graph id the server does not serve.
Behind it runs the real v4 desk with the fixture model; the ledger is a temp file through DATAFLOW_REFUNDS_PATH.
"""

from __future__ import annotations

import json
import runpy
import socket
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import httpx
import langgraph_sdk
import pytest
from langgraph.types import Command
from langgraph_sdk.errors import UnprocessableEntityError
from langgraph_sdk.schema import StreamPart

import config
from dataflow.graphs.v4_hitl import build_v4_hitl
from dataflow.ops import dev_server as ds
from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lab_copy import ROOT
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = ROOT / "labs" / "06_10_02_studio.py"
SERVED = json.loads((ROOT / "langgraph.json").read_text(encoding="utf-8"))["graphs"]
REPO_LEDGER = ROOT / "dataflow" / "data" / "refunds.jsonl"
REPLY = "Refund issued for order DF-1001. Amount: 49.0."

STANDIN = '''import subprocess, sys, time
port = sys.argv[1]
print("- API: http://127.0.0.1:" + port, flush=True)
print("- Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:" + port, flush=True)
print("- API Docs: http://127.0.0.1:" + port + "/docs", flush=True)
print("Starting In-Memory runtime with langgraph-api=9.9.9 and in-memory runtime=0.0.1", flush=True)
child = subprocess.Popen([sys.executable, sys.argv[2], port])
open(sys.argv[3], "w").write(str(child.pid))
while True:
    time.sleep(1)
'''

CHILD = '''import http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"ok":true}'
        self.send_response(200 if self.path == "/ok" else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
'''


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _alive(pid: int) -> bool:
    import psutil

    try:
        return psutil.Process(pid).is_running() and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


@pytest.fixture
def standin(tmp_path):
    (tmp_path / "standin.py").write_text(STANDIN, encoding="utf-8")
    (tmp_path / "child.py").write_text(CHILD, encoding="utf-8")
    port = _free_port()
    pidfile = tmp_path / "child.pid"
    command = [sys.executable, str(tmp_path / "standin.py"), str(port), str(tmp_path / "child.py"), str(pidfile)]
    return port, command, pidfile


def test_port_from_the_environment(monkeypatch):
    monkeypatch.delenv(ds.PORT_ENV, raising=False)
    assert ds.dev_port() == 2024
    monkeypatch.setenv(ds.PORT_ENV, "2186")
    assert ds.dev_port() == 2186
    argv = ds.dev_command(2186)
    assert Path(argv[0]).stem == "langgraph"
    assert argv[1:] == ["dev", "--no-browser", "--no-reload", "--port", "2186"]


def test_ready_urls_version_and_nothing_left(standin, tmp_path):
    pytest.importorskip("psutil")
    port, command, pidfile = standin
    with ds.dev_server(tmp_path, port=port, timeout=30, command=command) as server:
        assert server.ready and server.base_url == f"http://127.0.0.1:{port}"
        assert server.studio_url == f"https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:{port}"
        assert server.docs_url == f"http://127.0.0.1:{port}/docs"
        assert server.api_version == "9.9.9"
        child = int(pidfile.read_text(encoding="utf-8"))
        assert _alive(child) and ds.port_in_use(port)
    assert server.proc.poll() is not None
    deadline = time.monotonic() + 10
    while _alive(child) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not _alive(child), "the child that held the port is still running"
    assert not ds.port_in_use(port)


def test_stopped_when_the_block_raises(standin, tmp_path):
    port, command, _ = standin
    with pytest.raises(KeyError):
        with ds.dev_server(tmp_path, port=port, timeout=30, command=command):
            raise KeyError("the client failed")
    assert not ds.port_in_use(port)


def test_busy_port_is_refused_and_left_alone(tmp_path):
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        port = holder.getsockname()[1]
        with pytest.raises(RuntimeError, match=f"port {port} is already in use"):
            with ds.dev_server(tmp_path, port=port, timeout=5, command=[sys.executable, "-c", "pass"]):
                pass
        assert ds.port_in_use(port)


def test_a_server_that_never_starts(tmp_path):
    port = _free_port()
    command = [sys.executable, "-c", "print('ImportError: the server could not import its app', flush=True)"]
    with pytest.raises(RuntimeError) as caught:
        with ds.dev_server(tmp_path, port=port, timeout=10, command=command):
            pass
    assert f"server did not start on port {port}" in str(caught.value)
    assert "ImportError: the server could not import its app" in str(caught.value)


# ---- the lab, through a recording client ----------------------------------------------------------------------------
class _Threads:
    def __init__(self, owner):
        self.owner = owner

    def create(self):
        thread_id = str(uuid.uuid4())
        self.owner.calls.append(("threads.create", thread_id))
        return {"thread_id": thread_id}

    def get_state(self, thread_id):
        snap = self.owner.graph.get_state(self.owner.cfg(thread_id))
        tasks = [
            {"name": task.name, "interrupts": [{"id": item.id, "value": item.value} for item in task.interrupts]}
            for task in snap.tasks
        ]
        return {"values": snap.values, "next": list(snap.next), "tasks": tasks}

    def get_history(self, thread_id, limit=10):
        return list(self.owner.graph.get_state_history(self.owner.cfg(thread_id)))[:limit]


class _Runs:
    def __init__(self, owner):
        self.owner = owner

    def _served(self, graph_id):
        if graph_id not in SERVED:
            detail = (f"Invalid assistant: '{graph_id}'. Must be either:\n- A valid assistant UUID, or\n"
                      f"- One of the registered graphs: {', '.join(SERVED)}")
            response = httpx.Response(422, json={"detail": detail}, request=httpx.Request("POST", "http://test/runs"))
            raise UnprocessableEntityError(detail, response=response, body={"detail": detail})

    def stream(self, thread_id, graph_id, *, input=None, stream_mode="values"):
        self.owner.calls.append(("runs.stream", graph_id, input, stream_mode))
        self._served(graph_id)
        yield StreamPart("metadata", {"run_id": "r1", "attempt": 1}, None)
        for chunk in self.owner.graph.stream(input, self.owner.cfg(thread_id), stream_mode=stream_mode):
            yield StreamPart("updates", chunk, None)

    def wait(self, thread_id, graph_id, *, command=None):
        self.owner.calls.append(("runs.wait", graph_id, command))
        self._served(graph_id)
        return self.owner.graph.invoke(Command(**command), self.owner.cfg(thread_id))


class _Assistants:
    def search(self):
        return [{"graph_id": graph_id, "name": graph_id} for graph_id in reversed(list(SERVED))]


class RecordingClient:
    """The SDK's sync client as far as the lab uses it, the real v4 desk behind it."""

    def __init__(self, route="refund"):
        self.graph = build_v4_hitl(model=FakeChatModel(route=route))
        self.calls = []
        self.threads, self.runs, self.assistants = _Threads(self), _Runs(self), _Assistants()

    @staticmethod
    def cfg(thread_id):
        return {"configurable": {"thread_id": thread_id}}


@pytest.fixture
def served_desk(monkeypatch, tmp_path):
    """The lab's server and client, faked at the two names the lab imports; returns what was started and stopped."""
    monkeypatch.setattr(config, "get_chat_model", lambda **k: FakeChatModel(route="refund"))
    monkeypatch.setenv("DATAFLOW_REFUNDS_PATH", str(tmp_path / "ledger" / "refunds.jsonl"))
    port = _free_port()
    monkeypatch.setenv(ds.PORT_ENV, str(port))
    monkeypatch.delenv("STUDIO_HOLD_SECONDS", raising=False)
    seen = {"clients": [], "started": [], "stopped": []}

    class _Server:
        base_url = f"http://127.0.0.1:{port}"
        studio_url = f"https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:{port}"
        docs_url = f"http://127.0.0.1:{port}/docs"
        api_version = "0.10.3"

    @contextmanager
    def fake_dev_server(root, port=None, timeout=90, command=None):
        seen["started"].append((Path(root), port))
        try:
            yield _Server()
        finally:
            seen["stopped"].append(port)

    def fake_client(url):
        client = RecordingClient()
        client.url = url
        seen["clients"].append(client)
        return client

    monkeypatch.setattr(ds, "dev_server", fake_dev_server)
    monkeypatch.setattr(langgraph_sdk, "get_sync_client", fake_client)
    seen["port"] = port
    return seen


def _ledger_state():
    return REPO_LEDGER.read_bytes() if REPO_LEDGER.exists() else None


def _run(path, capsys):
    lab = runpy.run_path(str(path), run_name="__main__")
    return lab, capsys.readouterr().out.splitlines()


def test_the_lab_graph_id_is_the_served_desk():
    text = LAB.read_text(encoding="utf-8")
    assert 'GRAPH_ID = "desk"\n' in text
    assert SERVED["desk"] == "./dataflow/graphs/v4_hitl.py:graph"
    assert sorted(SERVED) == ["desk", "nightly", "replay", "team"]


def test_lab_parks_and_resumes_through_the_client(served_desk, capsys):
    before = _ledger_state()
    _, out = _run(LAB, capsys)
    # The desk runs in this process behind the recording client, so the package's actor= line lands here; through the
    # real server it is in the server's log, not the lab's output.
    out = [line for line in out if not line.startswith("actor=")]
    port = served_desk["port"]
    assert out[1:3] == ["langchain-core 1.6.2", "langgraph 1.2.11"]
    assert out[3].startswith("langgraph-api ") and out[4].startswith("langgraph-sdk ")
    assert [line for line in out if line.startswith("served ")] == [f"served {k} {v}" for k, v in SERVED.items()]
    assert "desk_nodes ['classify', 'lookup', 'policy', 'refund']" in out
    start = out.index(f"api http://127.0.0.1:{port}")
    assert out[start : start + 15] == [
        f"api http://127.0.0.1:{port}",
        f"studio https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:{port}",
        f"docs http://127.0.0.1:{port}/docs",
        "served_by langgraph-api 0.10.3",
        "assistants ['desk', 'nightly', 'replay', 'team']",
        "update ['classify']",
        "update ['__interrupt__']",
        "next ['refund']",
        "question Approve this refund of 49.0 on order DF-1001?",
        "rows_while_parked 0",
        "reviewer answers approve",
        f"reply {REPLY}",
        "next []",
        "checkpoints 4",
        "refunds_rows 1",
    ]
    assert out[-1] == f"server_stopped port {port} free True"
    assert served_desk["started"] == [(ROOT, port)] and served_desk["stopped"] == [port]
    client = served_desk["clients"][0]
    assert client.url == f"http://127.0.0.1:{port}"
    assert [call[:2] for call in client.calls if call[0] != "threads.create"] == [
        ("runs.stream", "desk"), ("runs.wait", "desk")]
    assert client.calls[-1][2] == {"resume": "approve"}
    assert _ledger_state() == before


def test_typed_client_reject_on_a_fresh_thread(served_desk, capsys):
    lab, _ = _run(LAB, capsys)
    client = RecordingClient()
    thread_id = lab["run_to_the_pause"](client, "desk", "Refund order DF-1001 please")
    final = lab["answer"](client, thread_id, "desk", "reject")
    assert final["reply"].startswith("Refund declined for order DF-1001.")
    lookup = RecordingClient(route="lookup")
    lab["run_to_the_pause"](lookup, "desk", "Where is order DF-1002?")
    out = capsys.readouterr().out.splitlines()
    assert out[-3:] == ["update ['classify']", "update ['lookup']", "next []"]


def test_break_unknown_graph_id_is_refused_and_the_server_stopped(served_desk, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, 'GRAPH_ID = "desk"\n', 'GRAPH_ID = "desks"\n')
    (tmp_path / "langgraph.json").write_bytes((ROOT / "langgraph.json").read_bytes())
    with pytest.raises(UnprocessableEntityError, match="Invalid assistant: 'desks'") as caught:
        _run(broken, capsys)
    assert caught.value.response.status_code == 422
    assert "One of the registered graphs: desk, team, nightly, replay" in str(caught.value)
    assert served_desk["stopped"] == [served_desk["port"]]
    out = capsys.readouterr().out
    assert "update [" not in out and "refunds_rows" not in out