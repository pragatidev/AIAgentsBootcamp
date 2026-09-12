# AI Agents Bootcamp workbench

Companion repo for the Udemy course AI Agents Bootcamp (listing 6521157).

Three builds:

- DataFlow desk: a LangGraph support desk with retrieve, a parked refund, citations, and a refuse line.
- Research and report agent: a plan, files, isolated subagents, and a sourced report on disk.
- TalentFlow pipeline: map-reduce over resumes, a job description, and email templates.

Four files a clone needs: README (this file), smoke (`deploy/smoke.py`), golden set (`eval/golden.jsonl`), the FastAPI door (`dataflow/serve/app.py`).

## Clone and test (no key)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.sample .env
pytest -q
```

macOS / Linux: `source .venv/bin/activate` then `cp .env.sample .env`. `pytest -q` must exit 0 with no cloud key. Live model calls skip without a key or Ollama.

## What the desk refuses

The DataFlow desk refuses when the knowledge base has nothing. It does not invent a policy. It does not write a refund until a named reviewer resumes the parked card.

For labs that call a model, install Ollama and run `ollama pull qwen3:8b`. Models live in `config.py`. Never commit `.env`. Capstones: `labs/19_dataflow/starter`, `labs/19_research/starter`, `labs/19_talentflow/starter`.

## Layout

```
techcorp/           IT desk (LangChain)
dataflow/           customer desk, graphs, RAG, MCP, FastAPI
talentflow/         resumes, job, email templates
research_agent/     research and report package
eval/golden.jsonl   golden set
deploy/smoke.py     clone smoke
labs/               teaching scripts plus .ipynb twins
tests/              green without a key
config.py           the only place a model id lives
_archive/2025_live/ 2025 listing notebooks. Not the learner path.
```

First lab: `labs/00_03_setup_check.py`. Twins: `python scripts/make_twins.py`. License MIT.
