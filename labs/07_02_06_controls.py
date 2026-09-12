# %% [markdown]
# Install both controls on the DataFlow refund path.
#
# When this works, schema_assert catches a missing amount, policy_judge
# is run on the same record, both costs are written to
# harness/control_class.md, and swapping them lets the schema error
# walk through. The assert is restored as the default.

# %%
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import config
from harness.sensors.policy_judge import policy_judge
from harness.sensors.schema_assert import SchemaError, schema_assert

print("model", config.CHAT_MODEL)

bad = {
    "order_id": "DF-1010",
    "reason": "duplicate charge",
}
print("planted_record", bad)
print("missing_field", "amount")

policy_text = (
    "Refund a duplicate charge once, for the order amount, with a reason. "
    "Do not refund an order that has already been refunded."
)

# %%
print("cell", 1)
assert_caught = None
started = time.perf_counter()
try:
    schema_assert(bad)
    print("assert_passed", True)
except SchemaError as exc:
    assert_caught = str(exc)
    print("assert_caught", True)
    print("assert_field", exc.field)
    print("assert_message", str(exc))
assert_ms = round((time.perf_counter() - started) * 1000, 3)
print("assert_ms", assert_ms)
print("assert_tokens", 0)

print("judge_on_same_record")
started_j = time.perf_counter()
judged = policy_judge(bad, policy_text)
judge_ms = round((time.perf_counter() - started_j) * 1000, 3)
print("judge_verdict", judged["verdict"])
print("judge_tokens", judged["tokens"])
print("judge_ms", judge_ms)
print("judge_text", judged["text"])
print("judge_usage", judged["usage"])

# %%
print("cell", 2)
control_path = root / "harness" / "control_class.md"
table = """# Control class

Measured on a planted refund record with the amount missing.

| class | check | what it caught | cost |
| computational | schema_assert | field amount ({assert_msg}) | {assert_ms} ms, 0 tokens |
| inferential | policy_judge | verdict {verdict} | {judge_ms} ms, {tokens} tokens |

Rule: schema and allowlist first. Judge only where a computer cannot decide.
""".format(
    assert_msg=assert_caught or "none",
    assert_ms=assert_ms,
    verdict=judged["verdict"],
    judge_ms=judge_ms,
    tokens=judged["tokens"],
)
control_path.write_text(table, encoding="utf-8")
print("wrote", control_path.as_posix())
print(control_path.read_text(encoding="utf-8"))

# %% [markdown]
# break it on purpose

# %%
print("cell", 3)
# PLANTED MISS: the judge is the only check. A missing amount is not a
# policy question, so the schema error walks through.


def judge_only(record):
    return policy_judge(record, policy_text)


walked = judge_only(bad)
print("swap", "judge_only")
print("schema_error_walked_through", True)
print("judge_only_verdict", walked["verdict"])
print("judge_only_tokens", walked["tokens"])
print("amount_in_record", "amount" in bad)

# %% [markdown]
# restore

# %%
print("cell", 4)
print("default_check", "schema_assert")
try:
    schema_assert(bad)
    print("restored_assert_passed", True)
except SchemaError as exc:
    print("restored_assert_caught", exc.field)
    print("restored_assert_message", str(exc))
print("judge_stays_behind_the_assert", True)
