# AI Agents Bootcamp workbench

Companion repo for the Udemy course AI Agents Bootcamp (listing 6521157).

**Which branch do I need?** The course was rebuilt in September 2026 and this branch, `master`, is the rebuilt course: every lecture names a file under `labs/`, and each lab comes as a plain `.py` script and an `.ipynb` twin, so you can work in an editor or in a notebook. It is written as a real repo on purpose, because that is how agent products are built at work: modules, tests, config, evals and a deploy door, not one long notebook. Took the 2025 edition? Your notebooks are on the branch `original-2025`, exactly as you had them: `git fetch && git checkout original-2025`. That branch is archived and no longer updated.

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
```

The 2025 edition notebooks are not in this branch. They live on the branch `original-2025`.

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

First lab: `labs/00_03_setup_check.py`. Twins: `python scripts/make_twins.py`. License MIT.
