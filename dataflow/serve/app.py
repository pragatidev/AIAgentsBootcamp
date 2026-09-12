"""HTTP door for the thin DataFlow chat page.

health() stays importable with no extra packages. FastAPI is optional at
import time so clone-contract tests keep passing if the extra deps are
missing. S30 fills the page; S43 builds the richer UI.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from dataflow.graphs.rag_graph import REFUSE_TEMPLATE


def health() -> dict:
    return {"ok": True, "service": "dataflow"}


PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>DataFlow desk</title>
  <style>
    body { font-family: sans-serif; max-width: 40rem; margin: 2rem auto; }
    textarea { width: 100%; height: 6rem; }
    #answer { min-height: 3rem; white-space: pre-wrap; margin-top: 1rem; }
    .citation, .refuse, .parked { margin-top: 0.5rem; }
  </style>
</head>
<body>
  <h1>DataFlow desk</h1>
  <textarea id="q" placeholder="Ask the desk"></textarea>
  <p><button id="send">Send</button></p>
  <div id="answer"></div>
  <div id="extra"></div>
  <script>
    async function send() {
      const q = document.getElementById('q').value;
      const answer = document.getElementById('answer');
      const extra = document.getElementById('extra');
      answer.textContent = '';
      extra.innerHTML = '';
      const res = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: q})
      });
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buf += dec.decode(value, {stream: true});
        const parts = buf.split('\\n\\n');
        buf = parts.pop();
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data:')) continue;
          const payload = JSON.parse(line.slice(5).trim());
          if (payload.text) answer.textContent += payload.text;
          if (payload.citation) {
            const el = document.createElement('div');
            el.className = 'citation';
            el.textContent = payload.citation;
            extra.appendChild(el);
          }
          if (payload.refuse) {
            const el = document.createElement('div');
            el.className = 'refuse';
            el.textContent = 'REFUSE';
            extra.appendChild(el);
          }
          if (payload.parked) {
            const el = document.createElement('div');
            el.className = 'parked';
            el.textContent = 'parked';
            extra.appendChild(el);
          }
        }
      }
    }
    document.getElementById('send').addEventListener('click', send);
  </script>
</body>
</html>
"""


def use_fixture_model() -> bool:
    return os.environ.get("DATAFLOW_UI_MODEL", "").strip().lower() == "fixture"


def fixture_reply(question: str) -> dict[str, Any]:
    """Scripted page facts for Playwright. No Ollama."""
    q = (question or "").lower()
    if "refund" in q:
        return {
            "answer": "Refund parked for a reviewer.",
            "citation": None,
            "refuse": False,
            "parked": True,
            "interrupt": {
                "action": "refund",
                "order_id": "DF-1001",
                "amount": 89.0,
                "reason": "fixture park",
            },
        }
    unknown = (
        "coffee",
        "gym",
        "warranty",
        "lounge",
        "island",
        "cattle",
        "beans",
    )
    if any(word in q for word in unknown):
        return {
            "answer": REFUSE_TEMPLATE.format(q=question),
            "citation": None,
            "refuse": True,
            "parked": False,
        }
    return {
        "answer": "The customer return window is 30 days from delivery.",
        "citation": "dataflow/wiki/return_policy.md",
        "refuse": False,
        "parked": False,
    }


def real_reply(question: str) -> dict[str, Any]:
    """Run the desk. Refund-shaped tickets park through v4 interrupt."""
    from config import get_chat_model

    text = question or ""
    if "refund" in text.lower():
        from langgraph.checkpoint.memory import InMemorySaver

        from dataflow.graphs.v4_hitl import build_v4_hitl

        saver = InMemorySaver()
        graph = build_v4_hitl(model=get_chat_model(), checkpointer=saver)
        cfg = {"configurable": {"thread_id": "ui-" + uuid.uuid4().hex}}
        graph.invoke({"ticket": text}, cfg)
        state = graph.get_state(cfg)
        if state.interrupts:
            payload = state.interrupts[0].value
            return {
                "answer": "Waiting for a reviewer to confirm the refund.",
                "citation": None,
                "refuse": False,
                "parked": True,
                "interrupt": payload if isinstance(payload, dict) else {"value": payload},
            }
        values = state.values or {}
        return {
            "answer": str(values.get("reply") or ""),
            "citation": None,
            "refuse": False,
            "parked": False,
        }

    from dataflow.graphs.rag_graph import build_rag_graph

    graph = build_rag_graph(model=get_chat_model(), scope="all")
    state = graph.invoke({"question": text})
    reply = str(state.get("reply") or state.get("answer") or "")
    sources = list(state.get("sources") or [])
    citation = None
    if sources:
        first = sources[0]
        if isinstance(first, dict):
            citation = str(first.get("source") or "")
        else:
            citation = str(first)
    refused = "I do not have that in the knowledge base" in reply
    return {
        "answer": reply,
        "citation": citation or None,
        "refuse": refused,
        "parked": False,
    }


def desk_reply(question: str) -> dict[str, Any]:
    if use_fixture_model():
        return fixture_reply(question)
    return real_reply(question)


def _sse(payload: dict[str, Any]) -> str:
    return "data: " + json.dumps(payload) + "\n\n"


try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, StreamingResponse

    app = FastAPI(title="DataFlow desk")

    @app.get("/health")
    def health_route() -> dict:
        return health()

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(PAGE_HTML)

    @app.post("/chat")
    async def chat(request: Request) -> StreamingResponse:
        body = await request.json()
        question = str(body.get("question") or body.get("q") or "")

        async def generate():
            import asyncio

            result = await asyncio.to_thread(desk_reply, question)
            text = str(result.get("answer") or "")
            step = 8 if use_fixture_model() else 24
            delay = 0.12 if use_fixture_model() else 0.02
            for i in range(0, max(len(text), 1), step):
                chunk = text[i : i + step]
                if chunk:
                    yield _sse({"text": chunk})
                    await asyncio.sleep(delay)
            if result.get("citation"):
                yield _sse({"citation": result["citation"]})
            if result.get("refuse"):
                yield _sse({"refuse": "REFUSE"})
            if result.get("parked"):
                yield _sse(
                    {
                        "parked": True,
                        "payload": result.get("interrupt") or {},
                    }
                )
            yield _sse({"done": True})

        return StreamingResponse(generate(), media_type="text/event-stream")

except ImportError:
    app = None
