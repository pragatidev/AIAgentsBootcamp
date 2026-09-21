# %% [markdown]
# LLM as judge on DataFlow answers in LangSmith.
#
# Score three real answers: grounded, fluent-wrong, refuse. First pass
# has no must-cite-a-file rule. Second pass adds it. Then register the
# judge as an evaluator on a three-example dataset so the scores show
# in LangSmith.

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
from dataflow.graphs.rag_graph import REFUSE_TEMPLATE, build_rag_graph
from dataflow.tools.retrieve import get_index
from dataflow.tracing import langsmith_key_present
from eval.judges.langsmith_judge import (
    score_three,
    three_samples,
)
from eval.langsmith_dataset import print_experiment
from eval.runners.rag_metrics import run_agentic

print("model", config.CHAT_MODEL)

print("building_index")
get_index(scope="all")
print("index_ready")
graph = build_rag_graph(scope="all", grade_enabled=False, cite_node=None)

# %%
print("cell", "three_answers")
grounded_q = "What is the customer return window?"
refuse_q = "Do you sell coffee beans in the DataFlow shop?"
print("grounded_question", grounded_q)
grounded_result = run_agentic(grounded_q, graph=graph)
print("grounded_route", grounded_result.get("route"))
print("grounded_answer")
print(grounded_result.get("answer"))
print("refuse_question", refuse_q)
refuse_result = run_agentic(refuse_q, graph=graph)
print("refuse_route", refuse_result.get("route"))
print("refuse_answer")
print(refuse_result.get("answer"))

samples = three_samples(
    grounded_answer=str(grounded_result.get("answer") or ""),
    grounded_passages=list(grounded_result.get("passages") or []),
    refuse_answer=str(refuse_result.get("answer") or REFUSE_TEMPLATE.format(q=refuse_q)),
)
for sample in samples:
    print("sample", sample["id"])
    print("sample_answer")
    print(sample["answer"])

# %%
print("cell", "judge_without_must_cite")
first = score_three(samples, must_cite_file=False)
for row in first:
    print("score1", row["id"], row["score"])
    print("raw1", row["id"], row["raw"])
fluent_first = [row for row in first if row["id"] == "fluent_wrong"][0]
print("fluent_wrong_passed_first", fluent_first["score"] == 1)
print(
    "fluent_wrong_first_honest",
    "passed" if fluent_first["score"] == 1 else "did not pass",
)

print("cell", "judge_with_must_cite")
second = score_three(samples, must_cite_file=True)
for row in second:
    print("score2", row["id"], row["score"])
    print("raw2", row["id"], row["raw"])
fluent_second = [row for row in second if row["id"] == "fluent_wrong"][0]
print("fluent_wrong_failed_second", fluent_second["score"] == 0)
print("fluent_wrong_is_the_fail", fluent_second["score"] == 0)

if not langsmith_key_present():
    print("langsmith fallback no key")
    from labs._quiet_exit import quiet_exit

    quiet_exit()

# %%
print("cell", "evaluate_three")
from langsmith import Client
from langsmith import evaluate
from eval.judges.langsmith_judge import langsmith_evaluator
from eval.langsmith_dataset import ensure_dataset

client = Client()
dataset = ensure_dataset(client, "dataflow-judge-three")
created = []
for sample in samples:
    example = client.create_example(
        dataset_id=dataset.id,
        inputs={
            "id": sample["id"],
            "input": sample["question"],
            "kind": sample["kind"],
        },
        outputs={"kind": sample["kind"]},
        metadata={"lab": "09_01_07"},
    )
    created.append((sample, example))
    print("judge_example", sample["id"], getattr(example, "id", ""))

canned = {sample["id"]: sample for sample, _ in created}


def target(inputs):
    sample = canned[str(inputs.get("id"))]
    return {
        "answer": sample["answer"],
        "reply": sample["answer"],
        "passages": sample["passages"],
        "sources": sample["passages"],
    }


results = evaluate(
    target,
    data=[example for _, example in created],
    evaluators=[langsmith_evaluator(must_cite_file=True)],
    experiment_prefix="dataflow-judge-must-cite",
    client=client,
    max_concurrency=1,
)
print_experiment(results)
print("done", "three scores twice, fluent-wrong is the fail on the second run")
