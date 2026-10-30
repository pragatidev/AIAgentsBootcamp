# TechCorp IT desk

A LangChain 1.x `create_agent` desk for internal IT tickets: password resets, shared-folder access, and VPN questions the employee's record can answer. The employee a write acts on comes from the request envelope, `DeskContext`, never from the ticket text. `reset_password` is a pretend reset: it returns a random temporary password to the employee and writes an audit line to `techcorp/data/audit.jsonl` (created at run time, gitignored) that never carries the password. Nothing touches a real directory.

## Run it

Make and activate `.venv` as `INSTALL.md` says (Windows: `.venv\Scripts\activate`; macOS and Linux: `source .venv/bin/activate`), with Ollama serving `qwen3:8b`, then from the repo root:

```
python labs/05_26_portfolio_techcorp_desk.py
```

Or from Python:

```
from techcorp.agent.desk import build_techcorp_desk, handle_ticket

desk = build_techcorp_desk()
out = handle_ticket(
    desk,
    "Ticket TC-1001: I forgot my laptop password. Please reset it.",
    user_id="E-4101",
    thread_id="demo",
    decision={"decisions": [{"type": "approve"}]},
)
print(out["parked"], out["reply"])
```

`build_techcorp_desk()` with no middleware argument is the gated desk: a reset or a grant parks until a person decides, and `handle_ticket` resumes it with the decision you pass.

## Tests

No live model and no key: the fixtures in `tests/fixtures/fake_model.py` play the model.

```
python -m pytest tests/test_techcorp_tools.py tests/test_techcorp_desk.py tests/test_lab_05_24.py tests/test_lab_05_26.py tests/test_techcorp_readme.py -q
```

`pytest.ini` sets `pythonpath = .`, so the package imports from the repo root without an install step.

## Design decisions

1. The acting employee comes from the envelope. `acting_user` in `techcorp/tools/accounts.py` reads `DeskContext.user_id`; an empty envelope is a typed miss, and an id typed into the ticket that disagrees is ignored, marked `"mismatch": true` on the audit line and returned as `requested_user_id_ignored`. Tests: `test_context_id_beats_text`, `test_empty_envelope_is_a_typed_miss`, `test_mismatch_is_marked_in_the_audit`.
2. Every write tool parks for a person. `WRITE_TOOLS` in `techcorp/agent/desk.py` names `reset_password` and `grant_access`; `write_gate()` parks before each with four choices (approve, edit, reject, respond) and a description that names the employee the tool will act on. Test: `test_gate_names_are_real_tools`.
3. The desk is gated by default. `build_techcorp_desk()` with no middleware argument uses `DEFAULT_MIDDLEWARE` and an in-memory saver; an explicit list, even an empty one, is used as given. Test: `test_default_build_gates_reset`.
4. A run is capped at six tool calls (`ToolCallLimitMiddleware(run_limit=6)` in `DEFAULT_MIDDLEWARE`).
5. Refusals have one shape, written in `techcorp/agent/prompts.py`: `I cannot help with that from the IT desk: <reason>. Please contact <team>.`
6. The audit line never carries a secret. `SECRET_KEYS` in `techcorp/tools/accounts.py` drops the temporary password before a line is written; the line carries the action, the acting id, the id the model asked for, and the ticket and request ids when the envelope has them. Test: `test_audit_line_has_no_secret`.
7. Nothing builds a model at import. Test: `test_importing_the_package_builds_no_model`.

## Known limits

1. VPN: the desk answers what the employee's record holds (`lookup_user` returns `vpn_enabled` and groups). It has no tool for connection faults, so those go to Network Support in the refusal shape.
2. Software installs are not done here; they go to a person in the refusal shape.
3. The temporary password reaches the employee in the model's reply, and nothing filters what the model writes.
4. The tool's audit line says who asked (`by` on a grant), not who approved. The approver is on the run audit row in `techcorp/data/run_audit.jsonl` only when `RunAudit` and `ApproverRequired` from `techcorp/agent/middleware.py` are in the middleware list (lab `labs/05_28_custom_middleware.py`); `DEFAULT_MIDDLEWARE` does not include them.
5. The rules for who may call what live in `techcorp/agent/permissions.py` (roles, region, the share list in `techcorp/data/shares.json`) and run as `PermissionGate` (lab `labs/05_30_permissions_and_tenants.py`). `DEFAULT_MIDDLEWARE` does not include it, so the default desk grants any share the model names once a person approves.
6. A parked run lives in an in-memory saver; it is gone when the process ends.
7. One company, one in-memory directory for everyone.
8. The local model: see the last section.

## Sample run

What `python labs/05_26_portfolio_techcorp_desk.py` printed on 2026-10-30 on `qwen3:8b` (local Ollama), check lines only; the model's sentences differ from run to run:

```
gated reset_password ['approve', 'edit', 'reject', 'respond']
gated grant_access ['approve', 'edit', 'reject', 'respond']
reset_parked True
reset_reply_has_token True
vpn_refused_in_shape True
oos_refused_in_shape True
audit_lines_added 1
```

## What create_agent cannot do here, and why the DataFlow desk is a graph

`create_agent` (in `langchain/agents/factory.py`, LangChain 1.4.0) builds one loop: a model node, a tools node, and the cycle between them. Middleware adds to it more than it looks: each `before_agent`, `before_model`, `after_model` and `after_agent` hook becomes a named node in the graph, a middleware can add its own state keys through `state_schema`, and a hook declared with `can_jump_to` can send the run to the model, the tools or the end. This desk's gate already works that way: it parks the run on a named tool.

What it still cannot do:

1. A path of your own. A refund route with several steps of its own, or a supervisor that hands work between desks, is not one of the three jump targets.
2. A step anywhere else. Hooks sit at those four fixed points, and the only retries are for model calls and tool calls.
3. The model's own choice inside the loop has no name you can test alone; this repo's desk tests run the whole desk.

The DataFlow desk needs routes, a parked refund path and a supervisor, so the course draws it as a LangGraph graph. The tools, schemas, prompt and middleware from this package drop into that graph unchanged.

## Local model quality

Labs call `qwen3:8b` on Ollama for real. A small local model will skip a tool, think until it runs out of room and return an empty reply, or refuse in the wrong shape on some tickets. That is a property of the weights, not of the package. The pytest suite is the clone contract: it stays green with the fixture models and no key. Treat a live lab transcript as one run, not as a guarantee.
