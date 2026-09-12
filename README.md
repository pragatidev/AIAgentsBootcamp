# AI Agents Bootcamp workbench

Companion repo for the Udemy course AI Agents Bootcamp (listing 6521157).

Three portfolio worlds, one package each:

- **TechCorp** (`techcorp/`) is the IT desk. LangChain. Password reset, VPN, software install.
- **DataFlow** (`dataflow/`) is the customer knowledge desk. LangGraph and RAG. Orders, tickets, a 20-file knowledge base.
- **TalentFlow** (`talentflow/`) is resumes, a job description, and email templates. Parallel and map-reduce.

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

Course: https://www.udemy.com/course/ai-agents-bootcamp-build-with-langchain-rag-langflow-gpt/

## Layout

```
techcorp/      IT desk (Part 5)
dataflow/      customer desk, graphs, knowledge base, ambient inbox (Parts 6, 8, 12, 17)
talentflow/    resumes and templates (6.7, capstone 3)
research_agent/  Deep Agents research and report package (6.11)
dataflow/ambient/  file watcher and inbox (6.12)
dataflow/graphs/v8_nightly.py  nightly triage (6.12)
labs/          numbered teaching scripts (Run Cell on # %%) plus .ipynb twins
config.py      the only place a model id lives
docs/CURRENCY.md
tests/         green without a key
scripts/make_twins.py
_archive/2025_live/   2025 listing notebooks. They are not the path you follow.
```

Labs ship twice: `labs/NN_slug.py` for VS Code Run Cell, and a notebook twin from `python scripts/make_twins.py`.

`initialize_agent` does not ship. `create_react_agent` does not ship.

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
