# AI Agents Bootcamp

Companion repo for the Udemy course
https://www.udemy.com/course/ai-agents-bootcamp-build-with-langchain-rag-langflow-gpt/

Clone this folder. Open the notebooks in `Section_*` as the lectures tell you. Every notebook loads the model with `get_llm()` from `.env`. You do not paste a key into a cell.

## Setup

Python 3.11 or 3.12.

```
git clone https://github.com/pragatidev/AIAgentsBootcamp.git
cd AIAgentsBootcamp
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

`pytest -q` must exit 0 with no cloud key.

Then edit `.env`. For learning, leave `PREFERRED_PROVIDER=ollama` and run `ollama pull llama3.2`. For Claude or GPT, paste the key and set `PREFERRED_PROVIDER` to `anthropic` or `openai`. Never commit `.env`.

Open the repo root in VS Code or Jupyter. If this folder sits inside another project, the first notebook cell still finds it.

## What you open in class

- `Section_1_Introduction` through `Section_12_Bonus_Future_of_AI_Agents` — the live lectures
- Portfolio notebooks: TechCorp IT chatbot, TalentFlow HR, DataFlow RAG, SupportFlow, LangGraph document pipeline
- `src/llm.py` — `get_llm()`, `get_embeddings()`, `get_autogen_config()`
- `src/paths.py` — finds this repo at clone-root or nested
- `labs/` and `northstar/` — the 2026 package growing beside the live notebooks

## Layout

```
Section_1_Introduction/ ... Section_12_...
Section_5_Autonomous_Workflows/data/resumes/
Section_6_Real_World_RAG_Engineering/enterprise_knowledge_base/
src/llm.py
.env.sample
labs/
northstar/
tests/
```

Course id 6521157. License MIT.
