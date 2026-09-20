"""Callbacks for one DataFlow run: hosted LangChainTracer, or local fallback.

Prints which tracer it picked. The word fallback appears only on the local path.
Never prints a key or a .env line.
"""

from __future__ import annotations

import os
import time
from typing import Any

from dataflow.ops.tracer import LocalTraceHandler, _langsmith_enabled


def load_env() -> None:
    """Load .env without printing values."""
    try:
        from src.paths import load_dotenv

        load_dotenv()
    except Exception:
        return


def langsmith_key_present() -> bool:
    key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not key:
        key = os.environ.get("LANGCHAIN_API_KEY", "").strip()
    return bool(key)


def key_present() -> bool:
    return langsmith_key_present()


def current_project() -> str:
    return (
        os.environ.get("LANGSMITH_PROJECT", "").strip()
        or os.environ.get("LANGCHAIN_PROJECT", "").strip()
        or "default"
    )


def langsmith_tracer_if_key(project_name: str | None = None) -> Any | None:
    """LangChainTracer when a key exists. None otherwise. Does not print."""
    if not langsmith_key_present():
        return None
    from langchain_core.tracers.langchain import LangChainTracer

    name = project_name if project_name is not None else current_project()
    return LangChainTracer(project_name=name)


def make_client() -> Any | None:
    if not langsmith_key_present():
        return None
    from langsmith import Client

    return Client()


def callbacks_for_run(project_name: str | None = None) -> list[Any]:
    """Callbacks for one invoke.

    Hosted LangChainTracer when LANGSMITH_TRACING is on and a key exists.
    Otherwise LocalTraceHandler, labelled fallback.
    """
    if _langsmith_enabled():
        tracer = langsmith_tracer_if_key(project_name=project_name)
        if tracer is not None:
            name = project_name if project_name is not None else current_project()
            print("tracer LangChainTracer project", name, flush=True)
            return [tracer]
    print("tracer LocalTraceHandler fallback", flush=True)
    return [LocalTraceHandler()]


def run_callbacks(project_name: str | None = None) -> list[Any]:
    return callbacks_for_run(project_name=project_name)


def retrieve_span_name(waterfall: str) -> str:
    """First span name that is retrieve, from a local waterfall."""
    for line in (waterfall or "").splitlines():
        stripped = line.strip()
        parts = stripped.split()
        if len(parts) >= 2 and parts[1] == "retrieve":
            return parts[1]
        if "retrieve" in stripped.split():
            for part in parts:
                if part == "retrieve":
                    return part
    return ""


def flush_hosted_traces() -> None:
    """Wait until LangSmith has the batched runs. No-op if tracing is off."""
    try:
        from langchain_core.tracers.langchain import wait_for_all_tracers

        wait_for_all_tracers()
    except Exception as exc:
        print("flush_hosted_error", type(exc).__name__, exc, flush=True)
    try:
        from langsmith import Client

        if langsmith_key_present():
            Client().flush()
    except Exception as exc:
        print("client_flush_error", type(exc).__name__, exc, flush=True)


def newest_run(client: Any, project_name: str, *, tries: int = 8) -> Any | None:
    """Newest run in a project, from list_runs. None if the project is empty."""
    if client is None:
        return None
    last_error = None
    for _ in range(tries):
        flush_hosted_traces()
        try:
            runs = list(
                client.list_runs(project_name=project_name, is_root=True, limit=10)
            )
            if not runs:
                runs = list(client.list_runs(project_name=project_name, limit=10))
        except Exception as exc:
            last_error = exc
            runs = []
        if runs:
            runs.sort(
                key=lambda row: getattr(row, "start_time", None) or 0,
                reverse=True,
            )
            return runs[0]
        time.sleep(1.5)
    if last_error is not None:
        print("list_runs_error", type(last_error).__name__, last_error, flush=True)
    return None


def newest_root_run(client: Any, project_name: str, *, tries: int = 8) -> Any | None:
    return newest_run(client, project_name, tries=tries)


def make_client() -> Any | None:
    if not langsmith_key_present():
        return None
    from langsmith import Client

    return Client()


def print_hosted_run(run: Any, project_name: str | None = None) -> None:
    if run is None:
        print("sdk_run none", flush=True)
        return
    client = make_client()
    url = run_url(client, run, project_name=project_name) if client is not None else ""
    print("sdk_run_id", getattr(run, "id", None), flush=True)
    print("sdk_run_name", getattr(run, "name", None), flush=True)
    print("sdk_run_url", url, flush=True)


key_present = langsmith_key_present
run_callbacks = callbacks_for_run


def run_url(client: Any, run: Any, project_name: str | None = None) -> str:
    """URL the SDK returns. Empty string if it does not give one."""
    if run is None or client is None:
        return ""
    direct = getattr(run, "url", None)
    if direct:
        return str(direct)
    try:
        return str(client.get_run_url(run=run, project_name=project_name) or "")
    except Exception as exc:
        print("run_url_error", type(exc).__name__, exc, flush=True)
        return ""
