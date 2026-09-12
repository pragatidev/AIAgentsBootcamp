# %% [markdown]
# Run a child with a clean context and show the polluted miss.
#
# Score three documents in one context vs one child per document.
# Print both score sets and the polluted difference, honestly.

# %%
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from openai import OpenAI

import config

QUESTION = (
    "Score 0 to 10 how relevant this document is to a customer returning "
    "a purchased desk lamp. Reply as JSON list of "
    '{"name": file, "score": number, "reason": short}.'
)

DOCS = {
    "return_policy.md": (
        root / "dataflow" / "wiki" / "return_policy.md"
    ).read_text(encoding="utf-8")[:1500],
    "employee_handbook.txt": (
        root
        / "dataflow"
        / "knowledge_base"
        / "internal_operations"
        / "hr_policies"
        / "employee_handbook.txt"
    ).read_text(encoding="utf-8")[:1500],
    "shipping.md": (
        root / "dataflow" / "wiki" / "shipping.md"
    ).read_text(encoding="utf-8")[:1500],
}


def client() -> OpenAI:
    base = config.OLLAMA_BASE_URL.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    return OpenAI(base_url=base, api_key="ollama")


def ask(messages: list) -> str:
    resp = client().chat.completions.create(
        model=config.CHAT_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=400,
        extra_body={"think": False},
    )
    return resp.choices[0].message.content or ""


def parse_scores(raw: str) -> list:
    text = raw.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            return [{"raw": raw}]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return [json.loads(text[start : end + 1])]
        except json.JSONDecodeError:
            return [{"raw": raw}]
    return [{"raw": raw}]


# %%
bundle = "\n\n".join(f"FILE {name}\n{body}" for name, body in DOCS.items())
polluted_raw = ask(
    [
        {
            "role": "system",
            "content": "Score every document. Return JSON only.",
        },
        {"role": "user", "content": QUESTION + "\n\n" + bundle},
    ]
)
polluted = parse_scores(polluted_raw)
print("polluted_raw", polluted_raw)
print("polluted_scores", json.dumps(polluted, ensure_ascii=True))

# %%
isolated = []
for name, body in DOCS.items():
    raw = ask(
        [
            {
                "role": "system",
                "content": "Score this one document. Return JSON only.",
            },
            {
                "role": "user",
                "content": QUESTION + "\n\nFILE " + name + "\n" + body,
            },
        ]
    )
    parsed = parse_scores(raw)
    print("child", name)
    print("child_raw", raw)
    isolated.extend(parsed)
print("isolated_scores", json.dumps(isolated, ensure_ascii=True))

# %%
def score_of(rows: list, name: str):
    for row in rows:
        if isinstance(row, dict) and name.split(".")[0] in json.dumps(row):
            return row.get("score")
    return None


print("polluted_handbook", score_of(polluted, "employee_handbook.txt"))
print("isolated_handbook", score_of(isolated, "employee_handbook.txt"))
print("polluted_return", score_of(polluted, "return_policy.md"))
print("isolated_return", score_of(isolated, "return_policy.md"))
print(
    "polluted_difference",
    "handbook score in the one-context run vs the child that saw only the handbook",
)
