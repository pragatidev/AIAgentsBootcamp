# AI Agents Bootcamp workbench

Companion repo for the Udemy course AI Agents Bootcamp (listing 6521157).

Three portfolio worlds, one package each:

- TechCorp (`techcorp/`) is the IT desk. LangChain. Password reset, VPN, software install. The Playwright status tool and the malicious-page sandbox live in `techcorp/browser/` (Section 39). The coding-agent harness and sandbox live in `techcorp/harness/` (Section 40).
- DataFlow (`dataflow/`) is the customer knowledge desk. LangGraph and RAG. Orders, tickets, a 20-file knowledge base.
- TalentFlow (`talentflow/`) is resumes, a job description, and email templates. Parallel and map-reduce.

The Deep Agents research and report agent lives in `research_agent/`. It imports the DataFlow knowledge base and stands on its own.

Ambient DataFlow (Section 18) lives in `dataflow/ambient/` plus `dataflow/graphs/v8_nightly.py`. A dropped ticket file starts a thread. Parked refunds land in the inbox. The nightly graph fans the desk over the day's tickets and writes a report.

Models live in `config.py`, never in a lecture title. The student default is `qwen3:8b` on Ollama.

## Quickstart

```
python -m venv .venv
```

Windows:

```
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.sample .env
pytest -q
```

macOS / Linux:

```
source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
pytest -q
```

`pytest -q` must exit 0 with no cloud key. Live model calls skip without a key or Ollama.

For labs that call a model, install [Ollama](https://ollama.com) and run `ollama pull qwen3:8b`. Copy `.env.sample` to `.env` if you want a hosted key later. Never commit `.env`.

First lab: `labs/00_03_setup_check.py`. Then `labs/00_04_keys_and_config.py` and `labs/00_05_notebook_twin_demo.py`.

Course: https://www.udemy.com/course/ai-agents-bootcamp-build-with-langchain-rag-langflow-gpt/

## Layout

```
techcorp/      IT desk (Section 6)
techcorp/browser/  Playwright status tool, allowlist, malicious page sandbox (Section 39)
techcorp/harness/  coding-agent AGENTS.md, permissions, sandboxed loop (Section 40)
dataflow/      customer desk, graphs, knowledge base, context, memory, rag, ambient inbox
talentflow/    resumes and templates (capstone 3)
research_agent/  Deep Agents research and report package (Section 17)
dataflow/ambient/  file watcher and inbox (Section 18)
dataflow/graphs/v8_nightly.py  nightly triage (Section 18)
harness/       parts, guides, sensors, permissions (Sections 19 to 21)
eval/          golden set, runners, judges, thresholds, CI gate (Sections 28 and 29)
labs/          numbered teaching scripts (Run Cell on # %%) plus .ipynb twins
config.py      the only place a model id lives
docs/CURRENCY.md
tests/         green without a key
scripts/make_twins.py
_archive/2025_live/   2025 listing notebooks. They are not the path you follow.
```

Labs ship twice: `labs/NN_slug.py` for VS Code Run Cell, and a notebook twin from `python scripts/make_twins.py`.

Foundation labs (Udemy Sections 1 to 5) are numbered `00_` through `04_` as those lectures land. LangGraph labs stay on `06_`.

`initialize_agent` does not ship. `create_react_agent` does not ship.

## RAG (Part 8)

Local default embedder is `nomic-embed-text` on Ollama. Chat is `qwen3:8b`.

Build the FAISS index (writes `dataflow/data/faiss_index`, gitignored):

```
python -m dataflow.rag.faiss_index
```

Run the knowledge desk on three tickets (policy with a citation, unknown that refuses, order id that does not retrieve):

```
python labs/08_04_06_portfolio_knowledge_desk.py
```

Run naive vs agentic evals on `eval/questions.jsonl`:

```
python labs/08_04_05_rag_evals.py
```

## Evals (Part 10)

The golden set is `eval/golden.jsonl`. A run writes `eval/baseline.md` with `unique_tickets` at the top. Node tests live in `tests/test_nodes_dataflow.py`. Faithfulness is `eval/runners/faithfulness.py`.

```
python labs/10_01_03_golden_set.py
python labs/10_01_05_node_tests.py
python labs/10_01_07_fluent_wrong.py
python labs/10_02_02_eval_ci.py
python labs/10_02_04_regression.py
python labs/10_02_06_calibration.py
python scripts/eval_ci.py --fixture
```

CI: `.github/workflows/eval.yml` runs `scripts/eval_ci.py --fixture` on pull requests. Thresholds live in `eval/thresholds.toml`. Latency is reported, not tracked.

pgvector is optional. `docker compose up -d postgres` starts `pgvector/pgvector:pg16`. Labs skip cleanly when Docker is down.

## What you open in class

- `labs/` as the lectures tell you
- `dataflow/graphs/` as the graphs grow
- `techcorp/data/tickets.jsonl` and `dataflow/data/` for the desks
- `talentflow/data/` for the resume batch
- `_archive/2025_live/` only if you want the old listing notebooks. That folder is not the learner path.

Nightly triage, local scheduler (skips the sleep with `run_now=True` in the lab):

```
python labs/06_12_06_nightly_triage.py
```

That run writes `dataflow/data/reports/nightly-<date>.md` and parks refund threads the inbox can list. The hosted Agent Server cron (`client.crons.create`) is shown in the lab as code and is not executed here.

License MIT.
