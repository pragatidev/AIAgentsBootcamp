"""Run an async coroutine from sync lab and test code.

MCPAdapter and FastMCP bind session tasks to the event loop that
opened them. asyncio.run closes that loop, so the next tool call dies
with "Event loop is closed". Keep one loop for the process and run
every MCP coroutine on it.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def get_mcp_loop() -> asyncio.AbstractEventLoop:
    """The long-lived loop FastMCP sessions live on."""
    global _loop, _thread
    with _lock:
        if _loop is not None and _loop.is_running():
            return _loop
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=_run_loop,
            args=(loop,),
            name="dataflow-mcp-loop",
            daemon=True,
        )
        thread.start()
        _loop = loop
        _thread = thread
        return loop


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine on the long-lived DataFlow MCP loop."""
    loop = get_mcp_loop()
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        raise RuntimeError(
            "run_async called from the DataFlow MCP loop; await the coroutine instead"
        )
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def stop_mcp_loop() -> None:
    global _loop, _thread
    with _lock:
        loop = _loop
        thread = _thread
        _loop = None
        _thread = None
    if loop is None:
        return
    if loop.is_running():
        loop.call_soon_threadsafe(loop.stop)
    if thread is not None:
        thread.join(timeout=2)


atexit.register(stop_mcp_loop)
