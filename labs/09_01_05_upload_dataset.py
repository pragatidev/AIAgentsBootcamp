# %% [markdown]
# Upload a DataFlow dataset and run evaluate().
#
# Read eval/golden.jsonl, create dataset dataflow-golden (reuse if it
# exists), create examples, run one code evaluator. First pass leaves
# one row without a reference so the evaluator skips it. Then add the
# field and rerun. Print the experiment name, the url the SDK returns,
# and N scored.

# %%
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from src.paths import load_dotenv

load_dotenv(root)

import config
from dataflow.graphs.rag_graph import build_rag_graph
from dataflow.tools.retrieve import get_index
from dataflow.tracing import langsmith_key_present
from eval.langsmith_dataset import (
    DATASET_NAME,
    create_row_example,
    desk_target_factory,
    ensure_dataset,
    example_outputs,
    exact_source_or_refuse,
    load_named_rows,
    print_experiment,
)

ROW_IDS = ["policy-return", "policy-shipping", "refuse-coffee"]
MISSING_ID = "policy-shipping"

print("model", config.CHAT_MODEL)
print("dataset_name", DATASET_NAME)
rows = load_named_rows(ROW_IDS)
print("n_rows", len(rows))
for row in rows:
    print("golden_id", row.get("id"), "kind", row.get("kind"))

# %%
print("cell", "missing_reference_local")
from types import SimpleNamespace

missing_row = [row for row in rows if row.get("id") == MISSING_ID][0]
fake_run = SimpleNamespace(
    outputs={"answer": "five business days", "sources": [], "passages": []}
)
fake_example_empty = SimpleNamespace(outputs=None, inputs={"id": MISSING_ID})
skip = exact_source_or_refuse(fake_run, fake_example_empty)
print("missing_reference_score", skip.get("score"))
print("missing_reference_comment", skip.get("comment"))
filled = SimpleNamespace(outputs=example_outputs(missing_row), inputs={"id": MISSING_ID})
hit = exact_source_or_refuse(fake_run, filled)
print("filled_reference_score", hit.get("score"))
print("filled_reference_comment", hit.get("comment"))

if not langsmith_key_present():
    print("langsmith fallback no key")
    print("n_scored", 0)
    raise SystemExit(0)

# %%
print("cell", "upload")
from langsmith import Client
from langsmith import evaluate

client = Client()
dataset = ensure_dataset(client, DATASET_NAME)
examples_missing: list = []
for row in rows:
    include = str(row.get("id")) != MISSING_ID
    examples_missing.append(
        create_row_example(
            client,
            dataset.id,
            row,
            include_reference=include,
        )
    )

print("building_index")
get_index(scope="all")
print("index_ready")
graph = build_rag_graph(scope="all", grade_enabled=False, cite_node=None)
target = desk_target_factory(graph)

print("cell", "evaluate_missing_reference")
results_missing = evaluate(
    target,
    data=examples_missing,
    evaluators=[exact_source_or_refuse],
    experiment_prefix="dataflow-golden-missing-ref",
    client=client,
    max_concurrency=1,
)
print_experiment(results_missing)

# %%
print("cell", "add_reference_and_rerun")
missing_example = None
for example, row in zip(examples_missing, rows):
    if str(row.get("id")) == MISSING_ID:
        missing_example = example
        break
if missing_example is None:
    raise SystemExit("missing example was not created")
updated = client.update_example(
    getattr(missing_example, "id"),
    outputs=example_outputs(missing_row),
)
print("updated_example", getattr(missing_example, "id"))
print("updated_keys", list(updated.keys()) if isinstance(updated, dict) else type(updated).__name__)

examples_filled = list(client.list_examples(example_ids=[ex.id for ex in examples_missing]))
print("n_examples_rerun", len(examples_filled))
results_filled = evaluate(
    target,
    data=examples_filled,
    evaluators=[exact_source_or_refuse],
    experiment_prefix="dataflow-golden-scored",
    client=client,
    max_concurrency=1,
)
print_experiment(results_filled)
print("n_examples", len(examples_filled))
print("done", "experiment with N examples scored")
