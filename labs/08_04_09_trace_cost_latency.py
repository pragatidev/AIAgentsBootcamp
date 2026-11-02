# %%
"""Lab 25.9: a retrieve on a trace, and cost and latency per question.

What we build: one DataFlow question runs through the graph with the local tracer on, which writes one line
per span: each graph step with its time and each model call with its tokens. You type the function that
adds a trace up: tokens in and out, the number of model calls, and the time of each step. Then the same
question runs with grading off, so you can read what the grader costs.

What you learn: a retrieve is a span like any other, with the passages it returned and how long it took,
and the cost of a question is its model calls times their tokens. Grading reads every passage with the
model, so it is most of the calls. The local model has no per-token price; a cost appears only when you
set your provider's prices. Section 26 opens the full trace in LangSmith; Section 45 owns the cost report.

What will be true on your screen: the trace's retrieve span with its time and the sources it returned, one
line per model call with its tokens, your totals beside a meter that counted the calls itself
(calls_match_meter True), the time of each step, the cost line, and the same question with grading off and
its fewer calls. Then python -m pytest tests/test_lab_08_04_09.py -q passes.
"""

from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import config
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.ops.tracer import GRAPH_STEPS, traced_invoke
from eval.runners.rag_metrics import cost_line, meter


# %%
# TYPE THIS: trace_totals. The signature and docstring are given; you type the body.
# Its finished copy is trace_totals in dataflow/ops/tracer.py.
def trace_totals(trace_path) -> dict:
    """Totals for one traced run, read from its jsonl file: tokens (input, output, total) and the number of calls over the chat model spans, and the summed duration_ms of each graph step span (kind chain, name in GRAPH_STEPS)."""
    tokens = {"input": 0, "output": 0, "total": 0}
    model_calls = 0
    step_ms = {}
    for line in Path(trace_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        span = json.loads(line)
        if span.get("kind") == "chat_model":
            model_calls += 1
            for key in tokens:
                tokens[key] += int((span.get("tokens") or {}).get(key) or 0)
        elif span.get("kind") == "chain" and span.get("name") in GRAPH_STEPS:
            step_ms[span["name"]] = round(step_ms.get(span["name"], 0.0) + float(span.get("duration_ms") or 0.0), 2)
    return {"tokens": tokens, "model_calls": model_calls, "step_ms": step_ms}


# BREAK: count every span as a model call. Move model_calls += 1 out of the chat_model branch, to the line
# right after span = json.loads(line), run the lab and read calls_match_meter, then
# python -m pytest tests/test_lab_08_04_09.py -q. git checkout -- labs/08_04_09_trace_cost_latency.py puts it back.


# %%
chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
question = "Who can approve a refund under 30 days?"
print("question", question, "desk support_agent scope all")
with meter() as counted:
    state, trace_path = traced_invoke(build_rag_graph(model=chat, scope="all"), {"question": question})
spans = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line.strip()]
retrieve_span = next(span for span in spans if span.get("kind") == "chain" and span.get("name") == "retrieve")
print("retrieve_span_ms", retrieve_span["duration_ms"])
print("retrieved", [(Path(p["source"]).name, round(p["score"], 4)) for p in state.get("passages") or []])
for span in spans:
    if span.get("kind") == "chat_model":
        print("model_call", span.get("duration_ms"), "ms tokens", span.get("tokens"))


# %%
totals = trace_totals(trace_path)
print("tokens", totals["tokens"])
print("model_calls", totals["model_calls"], "meter_counted", counted.model_calls)
print("calls_match_meter", totals["model_calls"] == counted.model_calls)
print("step_ms", totals["step_ms"])
print(cost_line(totals["tokens"]["input"], totals["tokens"]["output"]))


# %%
# The same question with grading off: what the grader costs, read from a second trace.
_, plain_path = traced_invoke(build_rag_graph(model=chat, scope="all", grade_enabled=False), {"question": question})
plain = trace_totals(plain_path)
print("grade_off model_calls", plain["model_calls"], "tokens", plain["tokens"]["total"])
print("grade_on model_calls", totals["model_calls"], "tokens", totals["tokens"]["total"])
print("calls_the_grader_added", totals["model_calls"] - plain["model_calls"])
