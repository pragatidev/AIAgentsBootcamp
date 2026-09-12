# Labs

Teaching scripts. One idea per file. Open in VS Code and Run Cell on `# %%` blocks.

Curriculum labs are numbered Part.Section.Lecture. Older S1-S16 files stay while that spine is rewritten.

```
06_01_03_build_triage_graph.py   three-node DataFlow graph, mermaid, compile
06_01_04_invoke_and_test.py      invoke a real ticket, classify alone, pytest
01_setup.py          clone, pytest green, no key
02_read_a_loop.py    the loop before a framework
03_tokens.py         short vs stuffed prompt
04_walk_package.py   dataflow folders
05_call_hosted.py    SKIPPED without a key
05_call_local.py     SKIPPED without Ollama
05_swap_model.py     ids in config.py
06_bind_tools.py     typed tool schema
06_run_tool.py       DF-1001 hit, DF-9999 miss
07_first_loop.py     fixture agent, then the class
08_hello_graph.py    official START node END compile invoke
08_hidden_vs_graph.py hidden loop cannot test a node
08_run_graph.py      classify, lookup, reply
09_route.py          orders / policy / escalate
10_collision.py      InvalidUpdateError, then reducer
11_checkpoint.py     thread turns accrue, store across threads
12_interrupt.py      lookup free, refund parks, Command resume
13_stream.py         node updates
14_retrieve.py       wiki hit or refuse
15_parse.py          retry once, fail closed
16_cap.py            recursion_limit
```

The worlds are `techcorp/`, `dataflow/`, and `talentflow/`. These scripts teach. Pytest is the clone contract. Run `python scripts/make_twins.py` to refresh the notebook twins.
