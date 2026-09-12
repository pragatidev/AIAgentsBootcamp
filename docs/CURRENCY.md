# Currency. Verify at record time.

Nothing in this file is a promise that the id still exists tomorrow. Before a screen walk that prints a model name, open the provider console or `ollama list` and copy what is live into `config.py`.

Never put a model id in a lecture title.

## Local default (students)

- Runtime: Ollama at `http://localhost:11434`
- Chat tag to verify: `qwen3:8b` (env override `OLLAMA_CHAT_MODEL`)
- Why this tag: tool calling works, and the weights fit a 16 GB laptop
- No-tools fallback for Part 1 prints: `llama3.2:3b` (`NO_TOOLS_MODEL` in `config.py`)
- Embed tag to verify: `nomic-embed-text` (768 dims, env override `OLLAMA_EMBED_MODEL`)
- No key
- Every lecture capture that calls a model runs on this student default so the screen matches what the student sees. Pull `qwen3:8b` and prove tool calling with `scripts/probe_tool_calling.py` before the first Part 6 capture.

## Cloud (empty until a live lab)

Set the env var, then the id in `config.py`. Confirm the id in the vendor console the day you record. `get_chat_model()` uses OpenAI or Anthropic only when both a key and a model id are set.

- OpenAI chat: `OPENAI_CHAT_MODEL`
- Anthropic chat: `ANTHROPIC_CHAT_MODEL`

If the record machine has no key and the lecture needs a live call, HALT. Do not invent stdout. Local Ollama is enough for Part 6 captures.

## APIs that move

Verify these the week you record the matching lab:

- LangGraph 1.2: StateGraph, context_schema, Runtime, interrupt, checkpointer, store
- LangChain 1.4: create_agent, bind_tools, with_structured_output. Never create_react_agent, initialize_agent, or AgentExecutor
- deepagents 0.7.13: create_deep_agent, StateBackend, FilesystemBackend, TodoListMiddleware, isolated subagents
- MCP SDK and transports
- LangSmith vs a local tracer
- Docker base image for later deploy labs

Re-run the factory every 3-6 months. Re-record a screen walk when the UI changed.
