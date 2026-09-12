# %% [markdown]
# Tokens, the context window and cost.
#
# Count a short prompt and a stuffed one two ways: tiktoken cl100k_base
# as an approximation, and the model's own usage_metadata from a real
# call. Print the model card context length and the window this server
# actually applied. Then set a small num_ctx on purpose and print what
# spills.

# %%
from pathlib import Path
import json
import sys
import urllib.error
import urllib.request

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

import tiktoken

import config

enc = tiktoken.get_encoding("cl100k_base")
print("encoding", "cl100k_base")

SHORT = "Where is order DF-1002?"

KB_FILES = [
    root
    / "dataflow"
    / "knowledge_base"
    / "internal_operations"
    / "support_operations"
    / "customer_support_procedures.markdown",
    root
    / "dataflow"
    / "knowledge_base"
    / "customer_facing"
    / "product_user_guide.markdown",
    root
    / "dataflow"
    / "knowledge_base"
    / "customer_facing"
    / "troubleshooting_guide.txt",
]


def load_stuffed() -> str:
    chunks = [SHORT, "", "Knowledge base dump:"]
    for path in KB_FILES:
        chunks.append("")
        chunks.append("FILE " + path.name)
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


STUFFED = load_stuffed()
tiktoken_short = len(enc.encode(SHORT))
tiktoken_stuffed = len(enc.encode(STUFFED))
print("tiktoken_short", tiktoken_short)
print("tiktoken_stuffed", tiktoken_stuffed)
print("files", [p.name for p in KB_FILES])

# %%
def ollama_show(model_id: str) -> dict:
    url = config.OLLAMA_BASE_URL.rstrip("/") + "/api/show"
    body = json.dumps({"name": model_id}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def context_length_from_show(payload: dict) -> int | None:
    info = payload.get("model_info") or {}
    for key, value in info.items():
        if "context_length" in str(key).lower():
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    params = str(payload.get("parameters") or "")
    for line in params.splitlines():
        if "num_ctx" in line.lower():
            bits = line.split()
            for bit in reversed(bits):
                if bit.isdigit():
                    return int(bit)
    return None


def ollama_ps() -> dict | None:
    url = config.OLLAMA_BASE_URL.rstrip("/") + "/api/ps"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


show = ollama_show(config.CHAT_MODEL)
card_ctx = context_length_from_show(show)
print("model_card_context_length", card_ctx)
print("model_card_expected", 40960)

# %%
def usage_of(message) -> dict:
    meta = getattr(message, "usage_metadata", None) or {}
    return {
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "total_tokens": meta.get("total_tokens"),
    }


local = config.get_local_chat_model(reasoning=False, num_predict=32)
short_reply = local.invoke(SHORT)
print("usage_short", usage_of(short_reply))
print("tiktoken_short", tiktoken_short)
print("reply_short", getattr(short_reply, "content", ""))

# %%
stuffed_reply = local.invoke(STUFFED)
print("usage_stuffed", usage_of(stuffed_reply))
print("tiktoken_stuffed", tiktoken_stuffed)

ps = ollama_ps()
applied = None
if ps:
    for item in ps.get("models") or []:
        if config.CHAT_MODEL.split(":")[0] in str(item.get("name") or ""):
            size = item.get("size_vram") or item.get("size")
            ctx = item.get("context_length") or item.get("context")
            details = item.get("details") or {}
            applied = {
                "name": item.get("name"),
                "context": ctx,
                "parameter_size": details.get("parameter_size"),
                "size": size,
            }
            print("server_ps_entry", applied)
if applied and applied.get("context"):
    print("window_server_applied", applied.get("context"))
else:
    usage_in = usage_of(stuffed_reply).get("input_tokens")
    print("window_server_applied", usage_in)
    print(
        "window_note",
        "api/ps did not report a context length; printing the prompt tokens the server counted",
    )

# %%
SMALL_CTX = 512
tiny = config.get_local_chat_model(
    reasoning=False,
    num_predict=16,
    num_ctx=SMALL_CTX,
)
tiny_reply = tiny.invoke(STUFFED)
tiny_usage = usage_of(tiny_reply)
print("num_ctx_set", SMALL_CTX)
print("usage_small_ctx", tiny_usage)
print("tiktoken_stuffed", tiktoken_stuffed)
spill_count = max(0, tiktoken_stuffed - SMALL_CTX)
print("tokens_that_do_not_fit", spill_count)
ids = enc.encode(STUFFED)
kept = enc.decode(ids[:SMALL_CTX])
spilled = enc.decode(ids[SMALL_CTX:]) if len(ids) > SMALL_CTX else ""
print("kept_head", kept[:240].replace("\n", " "))
print("spilled_head", spilled[:240].replace("\n", " "))
print(
    "spill_means",
    "the stuffed dump is larger than num_ctx; the tail of the knowledge base never reaches the model",
)
