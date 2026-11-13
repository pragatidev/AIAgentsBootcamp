"""Start and stop `langgraph dev` from Python, for the Studio lab (18.2).

`langgraph dev` reads langgraph.json, starts the Agent Server in memory and serves the graphs it names on one port. The
lab needs the server up for a few seconds, a client run through it, and then the server gone. This module is the
plumbing: the command, the port, the wait until the server answers /ok, the URLs and the langgraph-api version read from
the server's own lines, and the stop.

Two rules hold every time:
- it never starts on a port something else already holds, and it never stops a process it did not start;
- it never leaves a server running: the server and every process under it are stopped in a finally, and the port is
  checked free after.

The port comes from DATAFLOW_DEV_PORT, else 2024, the docs' default. --no-reload keeps the server to the one process
tree this module started; a student running `langgraph dev` by hand in a terminal gets the reloading server, which is
what Studio editing wants.
"""

from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

__all__ = [
    "DEFAULT_PORT",
    "PORT_ENV",
    "DevServer",
    "dev_command",
    "dev_port",
    "dev_server",
    "langgraph_exe",
    "port_in_use",
]

DEFAULT_PORT = 2024
PORT_ENV = "DATAFLOW_DEV_PORT"
HOST = "127.0.0.1"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_URL = re.compile(r"https?://[^\s\x1b]+")
_API_VERSION = re.compile(r"langgraph[-_]api(?:_version)?=([0-9][0-9A-Za-z.\-]*)")


def dev_port() -> int:
    """The port this machine's lab server uses: DATAFLOW_DEV_PORT, else 2024."""
    raw = os.environ.get(PORT_ENV, "").strip()
    return int(raw) if raw else DEFAULT_PORT


def langgraph_exe() -> Path:
    """The langgraph command installed next to the Python that is running this code."""
    scripts = Path(sys.executable).resolve().parent
    for name in ("langgraph.exe", "langgraph"):
        if (scripts / name).is_file():
            return scripts / name
    return scripts / "langgraph"


def dev_command(port: int) -> list[str]:
    """The argv the helper runs: langgraph dev on one port, no browser, no reloader."""
    return [str(langgraph_exe()), "dev", "--no-browser", "--no-reload", "--port", str(port)]


def port_in_use(port: int, host: str = HOST) -> bool:
    """True when something accepts a connection on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


@dataclass
class DevServer:
    """One running `langgraph dev`, started by this module."""

    root: Path
    port: int
    command: list[str]
    lines: list[str] = field(default_factory=list)
    proc: subprocess.Popen | None = None
    ready: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _reader: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{HOST}:{self.port}"

    def log(self) -> str:
        with self._lock:
            return _ANSI.sub("", "\n".join(self.lines))

    def urls(self) -> list[str]:
        """Every URL the server printed, in order, trailing punctuation dropped."""
        return [url.rstrip(".,)") for url in _URL.findall(self.log())]

    @property
    def studio_url(self) -> str:
        return next((url for url in self.urls() if "studio" in url.lower()), "")

    @property
    def docs_url(self) -> str:
        return next((url for url in self.urls() if url.rstrip("/").endswith("/docs")), "")

    @property
    def api_version(self) -> str:
        """The langgraph-api version the running server names in its own log lines."""
        found = _API_VERSION.search(self.log())
        return found.group(1) if found else ""

    def start(self) -> None:
        if port_in_use(self.port):
            raise RuntimeError(
                f"port {self.port} is already in use; stop what holds it, or set {PORT_ENV} to a free port"
            )
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        kwargs: dict = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(
            self.command,
            cwd=str(self.root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            **kwargs,
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for raw in self.proc.stdout:
            with self._lock:
                self.lines.append(raw.rstrip("\n"))

    def wait_ready(self, timeout: float) -> bool:
        """Poll GET /ok until it answers, the process exits, or timeout seconds pass."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(self.base_url + "/ok", timeout=1) as resp:
                    if resp.status == 200:
                        self.ready = True
                        return True
            except Exception:
                time.sleep(0.3)
        return False

    def stop(self) -> None:
        """Stop the server and every process under it, then wait until the port is free."""
        proc = self.proc
        if proc is None:
            return
        if proc.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    capture_output=True,
                    check=False,
                )
            else:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        deadline = time.monotonic() + 10
        while port_in_use(self.port) and time.monotonic() < deadline:
            time.sleep(0.2)
        if port_in_use(self.port):
            raise RuntimeError(f"port {self.port} is still in use after the server was stopped")


@contextmanager
def dev_server(
    root: str | Path,
    port: int | None = None,
    timeout: float = 90,
    command: list[str] | None = None,
) -> Iterator[DevServer]:
    """Run `langgraph dev` in root for the length of a with block. Always stopped on the way out.

    Raises RuntimeError with the server's own last lines when it does not answer /ok within timeout seconds.
    """
    port = dev_port() if port is None else int(port)
    server = DevServer(root=Path(root), port=port, command=command or dev_command(port))
    server.start()
    try:
        if not server.wait_ready(timeout):
            if server.proc is not None and server.proc.poll() is not None and server._reader is not None:
                server._reader.join(timeout=5)
            tail = "\n".join(server.log().splitlines()[-15:]) or "(no server output)"
            raise RuntimeError(f"server did not start on port {port}; its last lines:\n{tail}")
        yield server
    finally:
        server.stop()
