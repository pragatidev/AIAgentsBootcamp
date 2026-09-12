# AI Agents Bootcamp workbench

Companion repo for the Udemy course AI Agents Bootcamp (listing 6521157).

Three portfolio worlds, one package each:

- TechCorp (`techcorp/`) is the IT desk. LangChain. Password reset, VPN, software install.
- DataFlow (`dataflow/`) is the customer knowledge desk. LangGraph and RAG. Orders, tickets, a 20-file knowledge base.
- TalentFlow (`talentflow/`) is resumes, a job description, and email templates. Parallel and map-reduce.

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
dataflow/      customer desk, graphs, knowledge base, context, memory
talentflow/    resumes and templates
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

## What you open in class

- `labs/` as the lectures tell you
- `dataflow/graphs/` as the graphs grow
- `techcorp/data/tickets.jsonl` and `dataflow/data/` for the desks
- `talentflow/data/` for the resume batch
- `_archive/2025_live/` only if you want the old listing notebooks. That folder is not the learner path.

License MIT.
