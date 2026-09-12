# TechCorp IT desk

A LangChain 1.x `create_agent` desk for internal IT tickets: password resets, share access, and VPN questions. The acting employee id rides in `DeskContext`, not in the prompt. `reset_password` is a pretend reset. It writes a temporary token derived from the id and a counter, and an audit line at `techcorp/data/audit.jsonl` (gitignored). Nothing touches a real directory.

## Run it

From the course repo root, with Ollama serving `qwen3:8b`:

```
d:\project\viralLoom\.venv\Scripts\python.exe labs/05_26_portfolio_techcorp_desk.py
```

Or from Python:

```
from techcorp.agent.desk import DEFAULT_MIDDLEWARE, build_techcorp_desk, run_ticket
from langgraph.checkpoint.memory import InMemorySaver

desk = build_techcorp_desk(middleware=DEFAULT_MIDDLEWARE, checkpointer=InMemorySaver())
print(run_ticket(desk, "Ticket TC-1002: VPN drops.", user_id="E-4102", thread_id="demo"))
```

A password reset parks until you resume with `Command(resume={"decisions": [{"type": "approve"}]})`. Look at `labs/05_14_hitl_middleware_on_reset.py` for the exact shape.

## Tests

No live model. The fixture in `tests/fixtures/fake_model.py` proposes tool calls.

```
d:\project\viralLoom\.venv\Scripts\python.exe -m pytest tests/test_techcorp_tools.py tests/test_techcorp_desk.py --override-ini addopts= -q
```

`pytest.ini` already sets `pythonpath = .` so the package imports.

## Why the DataFlow desk is a graph

`create_agent` builds one shape: a model node, a tools node, and the cycle between them. Middleware changes behaviour around that shape. Three things it cannot do, which is why Part 6 draws DataFlow as a graph:

1. No branch on a value you chose. A refund path that must hit a person is an edge you can point at, not a paragraph in a system prompt.
2. No step of your own. A named classify or trim node, with its own state keys and retry, is not a `before_model` hook.
3. No test of one step alone. TechCorp tests run the whole desk. DataFlow tests call `classify` with one ticket and assert one field.

The tools, schemas, prompt, and middleware from this package drop into that graph unchanged. The shape changes. The pieces do not.

## Local model quality

Labs call `qwen3:8b` on Ollama for real. A small local model will skip a tool, invent a user id, or refuse in the wrong shape on some tickets. That is a property of the weights, not of the package. The pytest suite is the clone contract: it stays green with the fixture model and no key. Treat a live lab transcript as a screen, not as a guarantee.
