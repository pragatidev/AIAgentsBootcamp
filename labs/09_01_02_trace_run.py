# %% [markdown]
# Trace a DataFlow run in LangSmith.
#
# dataflow/tracing.py picks LangChainTracer when a key is set, else the
# local fallback. A policy ticket goes through the knowledge desk.
# The local waterfall must show model, retrieve and generate. Then the
# SDK reads the same run back. First invoke has no project name so it
# lands in default. Second invoke sets the project to dataflow-desk.

# %%
from pathlib import Path
import os
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from src.paths import load_dotenv

load_dotenv(root)

import config
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.ops.tracer import render_waterfall, traced_invoke
from dataflow.tools.retrieve import get_index
from dataflow.tracing import (
    callbacks_for_run,
    current_project,
    flush_hosted_traces,
    newest_run,
    retrieve_span_name,
    run_url,
)

TICKET = "What is the customer return window?"
print("model", config.CHAT_MODEL)
print("ticket", TICKET)
print(
    "tracing_callbacks_types",
    [type(cb).__name__ for cb in config.tracing_callbacks()],
)

print("building_index")
get_index(scope="all")
print("index_ready")
graph = build_rag_graph(scope="all", grade_enabled=False, cite_node=None)


def invoke_traced(project_label: str, project_name: str | None) -> dict:
    print("cell", project_label, flush=True)
    print("process_project_before", current_project(), flush=True)
    callbacks = callbacks_for_run(project_name=project_name)
    cfg = {
        "callbacks": callbacks,
        "run_name": "dataflow-policy",
    }
    output, trace_path = traced_invoke(
        graph,
        {"question": TICKET},
        cfg,
        run_name="dataflow-policy",
    )
    local_id = Path(trace_path).stem
    waterfall = render_waterfall(trace_path)
    retrieve = retrieve_span_name(waterfall)
    print("local_run_id", local_id, flush=True)
    print("retrieve_span_name", retrieve, flush=True)
    print("route", output.get("route") if isinstance(output, dict) else None)
    print("reply")
    print(output.get("reply") if isinstance(output, dict) else output)
    print("waterfall", flush=True)
    print(waterfall, flush=True)
    kinds = []
    for line in waterfall.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            kinds.append(parts[0] + " " + parts[1])
        elif parts:
            kinds.append(parts[0])
    print("span_names", kinds, flush=True)
    has_model = "chat_model" in waterfall or "model" in waterfall
    has_retrieve = "retrieve" in waterfall
    has_generate = "generate" in waterfall
    print("has_model_span", has_model, flush=True)
    print("has_retrieve_span", has_retrieve, flush=True)
    print("has_generate_span", has_generate, flush=True)
    return {
        "local_id": local_id,
        "retrieve": retrieve,
        "trace_path": trace_path,
        "output": output,
    }


# %%
print("cell", "default_project")
saved_ls = os.environ.pop("LANGSMITH_PROJECT", None)
saved_lc = os.environ.pop("LANGCHAIN_PROJECT", None)
print("popped_LANGSMITH_PROJECT", saved_ls is not None)
print("process_project_after_pop", current_project())
try:
    first = invoke_traced("default", "default")
    flush_hosted_traces()
    hosted_project = "default"
    print("landed_project", hosted_project)
    try:
        from langsmith import Client

        client = Client()
        run = newest_run(client, hosted_project)
        if run is None:
            print("sdk_run", "none")
        else:
            url = run_url(client, run, project_name=hosted_project)
            print("sdk_run_id", run.id)
            print("sdk_run_name", run.name)
            print("sdk_run_url", url)
            print("sdk_session_id", getattr(run, "session_id", ""))
    except Exception as exc:
        print("sdk_read_error", type(exc).__name__, exc)
finally:
    if saved_ls is not None:
        os.environ["LANGSMITH_PROJECT"] = saved_ls
    if saved_lc is not None:
        os.environ["LANGCHAIN_PROJECT"] = saved_lc

# %%
print("cell", "named_project")
os.environ["LANGSMITH_PROJECT"] = "dataflow-desk"
os.environ["LANGCHAIN_PROJECT"] = "dataflow-desk"
print("process_project_set", current_project())
second = invoke_traced("dataflow-desk", "dataflow-desk")
flush_hosted_traces()
print("landed_project", "dataflow-desk")
try:
    from langsmith import Client

    client = Client()
    run = newest_run(client, "dataflow-desk")
    if run is None:
        print("sdk_run", "none")
    else:
        url = run_url(client, run, project_name="dataflow-desk")
        print("sdk_run_id", run.id)
        print("sdk_run_name", run.name)
        print("sdk_run_url", url)
        print("sdk_session_id", getattr(run, "session_id", ""))
except Exception as exc:
    print("sdk_read_error", type(exc).__name__, exc)

print("done", "waterfall plus sdk read")
