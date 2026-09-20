# %% [markdown]
# Commit a DataFlow prompt and label two runs.
#
# The graph still holds the hardcoded GENERATE_SYSTEM string. Push two
# Prompt Hub versions, pull the second, point the desk at it, then
# label a grounded run and a fluent-wrong run.

# %%
from pathlib import Path
import sys
from typing import Any

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from src.paths import load_dotenv

load_dotenv(root)

import config
from dataflow.graphs.rag_graph import GENERATE_SYSTEM, build_rag_graph
from dataflow.ops.tracer import traced_invoke
from dataflow.tools.retrieve import get_index
from dataflow.tracing import (
    current_project,
    flush_hosted_traces,
    key_present,
    make_client,
    newest_root_run,
    print_hosted_run,
    run_callbacks,
)
from eval.judges.langsmith_judge import FLUENT_WRONG_ANSWER
from eval.langsmith_prompts import (
    PROMPT_NAME,
    as_chat_prompt,
    extract_prompt_text,
    prompt_v1,
    prompt_v2,
    write_labels,
    write_local_prompt,
)
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

print("model", config.CHAT_MODEL)
print("key_present", key_present())
print("hardcoded_system")
print(GENERATE_SYSTEM)
print("hardcoded_holds_old_string", "say you do not have it." in GENERATE_SYSTEM)

v1 = prompt_v1()
v2 = prompt_v2()
write_local_prompt(v1)
print("local_prompt", write_local_prompt(v1).as_posix())
print("v1")
print(v1)
print("v2")
print(v2)

client = make_client()
commit_urls: list[str] = []
pulled_text = v2

if client is None:
    print("hosted skipped: no LangSmith key", flush=True)
    write_local_prompt(v2)
    pulled_text = v2
else:
    print("cell", "push_v1", flush=True)
    url1 = client.push_prompt(
        PROMPT_NAME,
        object=as_chat_prompt(v1),
        commit_description="DataFlow generate system, first refusal line",
    )
    print("prompt_commit_1", url1, flush=True)
    commit_urls.append(str(url1))
    print("cell", "push_v2", flush=True)
    write_local_prompt(v2)
    url2 = client.push_prompt(
        PROMPT_NAME,
        object=as_chat_prompt(v2),
        commit_description="Refusal line names the knowledge base",
    )
    print("prompt_commit_2", url2, flush=True)
    commit_urls.append(str(url2))
    pulled = client.pull_prompt(PROMPT_NAME)
    pulled_text = extract_prompt_text(pulled)
    print("pulled_prompt", flush=True)
    print(pulled_text, flush=True)
    print("pulled_has_v2_refusal", "knowledge base" in pulled_text, flush=True)

# %%
print("cell", "invoke_hardcoded_then_hub", flush=True)
print("building_index", flush=True)
get_index(scope="all")
print("index_ready", flush=True)
ticket = "What is the customer return window?"
old_graph = build_rag_graph(scope="all", grade_enabled=False, cite_node=None)
old_out = old_graph.invoke({"question": ticket})
print("old_reply", old_out.get("reply") if isinstance(old_out, dict) else old_out, flush=True)

hub_graph = build_rag_graph(
    scope="all",
    grade_enabled=False,
    cite_node=None,
    system_prompt=pulled_text,
)
project = current_project()
callbacks = run_callbacks(project_name=project)
cfg = {
    "configurable": {"thread_id": "lab-27-3-grounded"},
    "callbacks": callbacks,
}
hub_out, hub_path = traced_invoke(
    hub_graph,
    {"question": ticket},
    cfg,
    run_name="hub-grounded",
)
print("hub_reply", hub_out.get("reply") if isinstance(hub_out, dict) else hub_out, flush=True)
print("hub_trace", None if hub_path is None else Path(hub_path).as_posix(), flush=True)
flush_hosted_traces()

# %%
print("cell", "fluent_wrong_run", flush=True)

class PlantState(TypedDict, total=False):
    ticket: str
    reply: str


def plant_node(state: PlantState) -> dict[str, str]:
    return {"reply": FLUENT_WRONG_ANSWER}


builder = StateGraph(PlantState)
builder.add_node("generate", plant_node)
builder.add_edge(START, "generate")
builder.add_edge("generate", END)
plant_graph = builder.compile()
plant_cfg = {
    "configurable": {"thread_id": "lab-27-3-fluent-wrong"},
    "callbacks": run_callbacks(project_name=project),
}
plant_out, plant_path = traced_invoke(
    plant_graph,
    {"ticket": "Can I get a ninety-day refund on an unused lamp?"},
    plant_cfg,
    run_name="fluent-wrong",
)
print("fluent_wrong_reply", plant_out.get("reply") if isinstance(plant_out, dict) else plant_out, flush=True)
flush_hosted_traces()

labels = [
    {
        "id": "grounded",
        "key": "label",
        "value": "grounded",
        "ticket": ticket,
    },
    {
        "id": "fluent_wrong",
        "key": "label",
        "value": "fluent_wrong",
        "ticket": "Can I get a ninety-day refund on an unused lamp?",
    },
]

if client is None:
    dest = write_labels(labels)
    print("labels_path", dest.as_posix(), flush=True)
    print("feedback skipped: no LangSmith key", flush=True)
    raise SystemExit(0)

grounded_run = newest_root_run(client, project)
print("grounded_run", flush=True)
print_hosted_run(grounded_run, project_name=project)

import time

time.sleep(1.5)
fluent_run = newest_root_run(client, project)
print("fluent_run", flush=True)
print_hosted_run(fluent_run, project_name=project)

def _feedback(run: Any, value: str) -> Any:
    if run is None:
        print("feedback skipped: no run for", value, flush=True)
        return None
    fb = client.create_feedback(
        getattr(run, "id", None),
        key="label",
        value=value,
    )
    print("feedback_id", getattr(fb, "id", None), "value", value, flush=True)
    return fb

fb_grounded = _feedback(grounded_run, "grounded")
fb_fluent = _feedback(fluent_run, "fluent_wrong")
if grounded_run is not None:
    labels[0]["run_id"] = str(getattr(grounded_run, "id", "") or "")
    labels[0]["feedback_id"] = str(getattr(fb_grounded, "id", "") or "")
if fluent_run is not None:
    labels[1]["run_id"] = str(getattr(fluent_run, "id", "") or "")
    labels[1]["feedback_id"] = str(getattr(fb_fluent, "id", "") or "")
dest = write_labels(labels)
print("labels_path", dest.as_posix(), flush=True)
print("prompt_commits", commit_urls, flush=True)
write_local_prompt(v1)
print("prompt_file_restored", True, flush=True)
