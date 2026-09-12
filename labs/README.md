# Labs

Teaching scripts. One idea per file. Open in VS Code and Run Cell on `# %%` blocks.

Curriculum labs are numbered Part.Lecture. Older S1-S16 files stay while that spine is rewritten.

```
00_03_setup_check.py             python, venv, git branch, pytest exit
00_04_keys_and_config.py         local model call, hosted skip or hosted then local
00_05_notebook_twin_demo.py      three cells so the twin shows cells
01_04_tokens_and_window.py       tiktoken plus usage_metadata, window, spill
01_06_first_raw_api_call.py      OpenAI SDK against Ollama /v1, then LangChain
01_08_structured_output_raw.py   Pydantic TicketClass, one failure, one retry
01_10_raw_tool_call.py           tools list, raw tool_calls, run, blank description
01_14_swap_the_model.py          same agent code, two model ids, same shape
02_03_scratch_agent.py           plain loop, cap 8, TC-1001
02_04_second_tool.py             lookup then reset, VPN only lookup
02_06_break_the_loop.py          runaway, blank description, write gate
02_13_loop_as_a_class.py         ScratchAgent.run, pytest
03_02_context_rot.py             constraint at turn 4, needed at turn 30
03_03_measure_tokens.py          tokens before and after the death
03_05_map_file.py                FAT and MAP constants, written to disk
03_06_fat_vs_map.py              same ticket, both files, token delta
03_08_compaction.py              sawtooth of token counts
03_09_compare_compaction.py      compacted vs uncompacted totals
03_11_notes_file.py              notes.json after each turn
03_12_recover_from_notes.py      fact the summary dropped, recovered
03_14_just_in_time_read.py       read only on the ticket that needs it
03_16_subagent_isolation.py      polluted vs isolated scores
04_03_thread_memory.py           second turn uses the first
04_03_other_thread_break.py      same graph, other thread id, the desk is a stranger
04_05_summarizer.py              facts, actions, decisions, open questions
04_07_store_preference.py        preference across threads, profile, forget
04_07_forget_break.py            forget the profile, read on a new thread
04_08_similarity_recall.py       hits with scores inside a customer namespace
04_10_desk_remembers.py          two tickets one customer, third reads nothing
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
06_08_02_retry_and_error_handler.py  flaky carrier retries, then a typed miss
06_08_03_task_survives_crash.py  receipt @task, planted crash, resume
06_08_04_cache_and_defer.py      policy cache hits, then defer on/off
06_08_06_cap_a_runaway.py        recursion limit, RemainingSteps, timeout, spend
06_09_02_build_a_supervisor.py   supervisor, two specialists, writer parks
06_09_03_debug_a_failed_handoff.py  planted bad return, then the good path
06_09_05_handoffs_with_command.py  history on one thread, then parallel collision
06_09_06_overspawn_and_the_cap.py  planted loop, token climb, then the cap
06_10_02_studio.py               langgraph.json, langgraph dev, two graphs
06_10_03_read_a_failed_run.py    waterfall FAIL plus checkpoint rail
06_10_05_wire_the_tracer.py      tracing_callbacks, traced_invoke, pytest
06_11_02_create_deep_agent.py    virtual filesystem, stream events, todos
06_11_03_filesystem_and_todo.py  real folder backend, todo changes on disk
06_11_05_portfolio_research_agent.py  python -m research_agent, then pytest
06_12_02_wake_on_ticket_file.py  drop two json tickets, watch once, sqlite still holds the park
06_12_04_inbox_resolve.py        list parked rows, approve and reject, then the crossed resume
06_12_06_nightly_triage.py       v8 nightly report, inbox rows, hosted cron as code only
07_01_02_harness_parts.py        parts.md, cap prints STOPPED, planted runaway
07_01_04_failure_log.py          failing_ticket.json into the failure log
07_01_05_attribute_three.py      three diagnoses, one corrected bucket
07_02_02_guide.py                no/vague/tight guide on T-3005
07_02_04_sensor.py               refund_diff FAIL, then self-correct
07_02_06_controls.py             schema_assert vs policy_judge costs
07_03_02_permissions.py          actor off the list, blocked write
07_03_05_miss_to_test.py         xfail on the old desk, green with control

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
10_03_02_load_test.py    golden replay, p95 table, hung ticket marked
10_03_04_playwright_ui.py  early innerText flake, two tests green, screenshot
10_03_06_qa_checklist.py  empty path is the find, parked UI test, path filled
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
05_14_reject_with_message_break.py  reject the parked reset with a reviewer message
