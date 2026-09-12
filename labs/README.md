# Labs

Teaching scripts. One idea per file. Open in VS Code and Run Cell on `# %%` blocks.

Curriculum labs are numbered Part.Section.Lecture. Older S1-S16 files stay while that spine is rewritten.

```
06_01_03_build_triage_graph.py   three-node DataFlow graph, mermaid, compile
06_01_04_invoke_and_test.py      invoke a real ticket, classify alone, pytest
06_02_02_route_three_ways.py     three tickets, three labeled routes, mermaid
06_02_04_tool_cycle.py           ToolNode cycle: call, result, final answer
06_02_05_test_routes.py          pytest tests/test_dataflow_routes.py
06_02_06_command_vs_edge.py      Command versus a conditional edge, both mermaids
06_03_03_add_messages_on_the_thread.py  two turns, count grows per node
06_03_04_plant_a_collision.py    InvalidUpdateError, then both log lines
06_03_05_trim_and_summarize.py   token count before and after, plus summary
06_04_02_resume_thread.py        same thread_id, turn two continues turn one
06_04_03_sqlite_kill_and_resume.py  --start then --resume on checkpoints.sqlite
06_04_05_store_facts.py          preference written on A, read on B, miss on C
06_05_02_park_the_refund.py      refund parks, payload on screen, no jsonl row
06_05_03_resume_approve_reject.py  two threads, approve writes, reject does not
06_05_04_edit_state_before_resume.py  dict decision lowers the refund amount
06_05_06_policy_lookup_free_refund_parks.py  lookup free, refund parks, pytest
08_01_03_load_knowledge_base.py  twenty files, csv row, json ImportError
08_01_05_compare_two_chunkers.py  recursive vs heading, orphan counts, winner
08_02_02_index_faiss.py          FAISS retrieve billing row, wrong embedder
08_02_04_pgvector.py             refund row from Postgres, or BLOCKED ON DOCKER
08_02_06_bind_retrieve_tool.py   retrieve tool call, lookup, chitchat, empty description
08_03_03_agentic_rag_graph.py    paraphrase, grades, skip grade cites the handbook
08_03_05_corrective_rag.py       GRADE=wrong, REWRITE, REFUSE, GraphRecursionError
08_04_02_print_citations.py      reply names customer_support_procedures.markdown
08_04_04_refuse_on_empty.py      REFUSE vs FABRICATED
08_04_05_rag_evals.py            naive vs agentic table, fluent miss marked
08_04_06_portfolio_knowledge_desk.py  three tickets plus pytest test_rag_*.py
10_01_03_golden_set.py   twenty distinct tickets, baseline.md, pad does not count
10_01_05_node_tests.py   classify three tickets, refuse trap, wiring fix
10_01_07_fluent_wrong.py ninety-day plant: heuristic pass, claim check fail
10_02_02_eval_ci.py      eval_ci green on baseline, workflow is the gate
10_02_04_regression.py   worse chunker fails CI, mirror last_run never fails
10_02_06_calibration.py  ten labels vs judge, trust note per kind
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
