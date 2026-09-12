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
06_06_02_stream.py               values, updates, messages, then custom+updates
06_06_03_stream_events.py        stream_events v3 interrupt projections, then approve
06_06_05_fork.py                 fork before speak, original trail intact
06_06_06_full_run.py             lookup through, refund parks, approve, pytest
06_07_02_two_lookups_in_parallel.py  lookup and policy_search in one superstep
06_07_04_map_reduce_resumes.py   Send one score worker per TalentFlow resume
06_07_06_billing_subgraph.py     billing box, private keys, interrupt inside
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
