"""Retrieve as a LangGraph tool. FAISS by default, customer scope.

The description is one of the routing texts the model reads; the desk's
system prompt is the other. Which folders a search may see comes from the
caller's envelope (the runtime context's actor_id), never from an argument
the model fills: the tool has no folder argument, and a code caller's folder
can only narrow the caller's scope.
"""

from __future__ import annotations

from typing import Any

from langchain.tools import ToolRuntime, tool

import config
from dataflow.rag.faiss_index import (
    INDEX_DIR,
    build_faiss_index,
    current_files,
    load_faiss_index,
    refresh_index,
    search,
)
from dataflow.rag.load import KB_DIR, WIKI_DIR, load_knowledge_base, relative_source
from dataflow.rag.manifest import diff, embedder_identity, file_hash, load_manifest, save_manifest

RETRIEVE_DESCRIPTION = (
    "Search the DataFlow customer policies and guides (wiki and customer facing pages) "
    "for a customer question. Returns passages with their source file."
)

CUSTOMER_FOLDERS = frozenset({"wiki", "customer_facing"})

# Who may read which folders. Folders are the honest unit here: the repo has one
# company and no tenant field. A real multi-tenant store also carries a tenant id on
# every row, with its keys and logs kept apart.
SCOPES = {
    "customer": CUSTOMER_FOLDERS,
    "support_agent": frozenset(
        {"wiki", "customer_facing", "business_data", "internal_operations", "legal_compliance"}
    ),
}
# The actor names are Section 31's table (dataflow/guardrails/allowlist.py). An
# actor the table does not know reads as a customer, the lowest scope, never the highest.
ACTOR_SCOPE = {
    "anon": "customer",
    "reviewer-1": "support_agent",
    "reviewer-2": "support_agent",
    "desk-lead": "support_agent",
}
# Which index each scope searches.
SCOPE_INDEX = {"customer": "customer", "support_agent": "all"}

# Two indexes, one per scope, each built from its own folders only. The
# customer index holds the wiki and the customer facing pages, nothing else,
# so an internal page is not in the index a customer's question searches.
# The "all" index holds every knowledge base folder, internal ones included,
# for the graphs built with scope="all". Each index carries index_meta.json:
# get_index rebuilds an index built from other folders or another embedder,
# and refreshes one whose files changed, so lab order cannot change what a
# scope sees. Labs that build their own index write to their own folder.
INDEX_ALL_DIR = INDEX_DIR.parent / "faiss_index_all"
SCOPE_ROOTS = {
    "customer": (KB_DIR / "customer_facing", WIKI_DIR),
    "all": (KB_DIR, WIKI_DIR),
}
SCOPE_DIRS = {"customer": INDEX_DIR, "all": INDEX_ALL_DIR}

_INDEX: Any = None
_INDEX_ALL: Any = None


def set_index(index: Any) -> None:
    """Tests inject a hashing index so pytest stays off Ollama. Both scopes."""
    global _INDEX, _INDEX_ALL
    _INDEX = index
    _INDEX_ALL = index


def reset_index() -> None:
    global _INDEX, _INDEX_ALL
    _INDEX = None
    _INDEX_ALL = None


def _roots_names(scope: str) -> list[str]:
    return [relative_source(root) for root in SCOPE_ROOTS[scope]]


def build_scope_index(scope: str, embeddings: Any = None):
    """Build one scope's index from that scope's folders only, and record them in index_meta.json."""
    index_dir = SCOPE_DIRS[scope]
    index = build_faiss_index(
        docs=load_knowledge_base(roots=SCOPE_ROOTS[scope]),
        index_dir=index_dir,
        embeddings=embeddings,
    )
    meta = load_manifest(index_dir) or {}
    meta.update({"scope": scope, "roots": _roots_names(scope)})
    save_manifest(index_dir, meta)
    return index


def stale_reason(scope: str, embeddings: Any) -> str | None:
    """Why the index on disk cannot be served as it is, or None when it can be loaded."""
    index_dir = SCOPE_DIRS[scope]
    if not (index_dir / "index.faiss").is_file():
        return "no index on disk yet"
    meta = load_manifest(index_dir)
    if meta is None:
        return "the index on disk has no index_meta.json, so nothing says what built it"
    if meta.get("scope") != scope or meta.get("roots") != _roots_names(scope):
        return "the index on disk was built from other folders"
    if meta.get("embedder") != embedder_identity(embeddings):
        return "the index on disk was built by another embedder"
    return None


def open_scope_index(scope: str, embeddings: Any = None):
    """Load a scope's index, rebuilding or refreshing it first when its manifest says so. Prints one line when it does."""
    embeddings = embeddings or config.get_embeddings()
    reason = stale_reason(scope, embeddings)
    if reason is not None:
        print("rebuilding_index", scope, reason, flush=True)
        return build_scope_index(scope, embeddings)
    index_dir = SCOPE_DIRS[scope]
    index = load_faiss_index(index_dir, embeddings=embeddings)
    meta = load_manifest(index_dir) or {}
    files = {source: file_hash(path) for source, path in current_files(SCOPE_ROOTS[scope]).items()}
    if any(diff(meta, files).values()):
        result = refresh_index(index, index_dir, SCOPE_ROOTS[scope])
        print(
            "refreshed_index",
            scope,
            "changed",
            result["added"] + result["changed"] + result["removed"],
            "embedded",
            result["embedded"],
            flush=True,
        )
    return index


def get_index(embeddings: Any = None, scope: str = "customer"):
    """Load the FAISS index for a scope, building it on first use.

    scope="customer" is the index under INDEX_DIR, built from the wiki and the
    customer facing pages. scope="all" is the full knowledge base under
    INDEX_ALL_DIR. A stale index is rebuilt or refreshed before it is served.
    """
    global _INDEX, _INDEX_ALL
    if scope == "all":
        if _INDEX_ALL is None:
            _INDEX_ALL = open_scope_index("all", embeddings)
        return _INDEX_ALL
    if _INDEX is None:
        _INDEX = open_scope_index("customer", embeddings)
    return _INDEX


def scope_for(ctx: Any) -> str:
    """The caller's scope from the envelope. No envelope, or an unknown actor, is the customer scope."""
    actor = getattr(ctx, "actor_id", None) if ctx is not None else None
    return ACTOR_SCOPE.get(str(actor), "customer") if actor else "customer"


def allowed_folders(ctx: Any) -> frozenset[str]:
    """The folders this caller may read, decided by the envelope before any search runs."""
    return SCOPES[scope_for(ctx)]


def scoped_folders(ctx: Any, requested: str | None = None) -> frozenset[str] | dict:
    """The caller's folders, or one of them when requested. A folder outside the scope is a typed miss."""
    allowed = allowed_folders(ctx)
    if not requested:
        return allowed
    if requested not in allowed:
        return {"found": False, "reason": f"folder {requested} is outside this caller's scope"}
    return frozenset({requested})


def _scope_name(scope: str) -> str:
    return "support_agent" if scope in ("all", "support_agent") else "customer"


_PG_STORE: Any = None


def get_pg_store():
    """The pgvector collection the retrieve path reads (config.PGVECTOR_COLLECTION), opened once per process."""
    global _PG_STORE
    if _PG_STORE is None:
        from dataflow.rag.pgvector_store import build_pgvector_store

        _PG_STORE = build_pgvector_store(config.PGVECTOR_COLLECTION, embeddings=config.get_embeddings())
    return _PG_STORE


def set_pg_store(store: Any) -> None:
    """Labs and tests hand in the store they opened. None forgets it."""
    global _PG_STORE
    _PG_STORE = store


def _faiss_rows(question: str, k: int, scope_name: str, folders: frozenset[str]) -> list[dict]:
    index = get_index(scope=SCOPE_INDEX[scope_name])
    fetched = search(index, question, k=max(k * 10, 32), folder=None)
    return [row for row in fetched if row.get("folder") in folders][:k]


def _pgvector_rows(question: str, k: int, folders: frozenset[str]) -> list[dict]:
    from dataflow.rag.pgvector_store import query

    return query(get_pg_store(), question, k=k, filter={"folder": {"$in": sorted(folders)}})


def retrieve_passages(
    question: str,
    k: int = 3,
    folder: str | None = None,
    *,
    scope: str = "customer",
    store: str | None = None,
) -> list[dict] | dict:
    """Search the scope's index. folder=None keeps the whole scope; a folder can only narrow it.

    scope is the caller's scope ("customer", or "support_agent" for every folder),
    set by code from the envelope, never by the model. A folder outside it returns
    the typed miss {"found": False, "reason": ...}. store is "faiss" or "pgvector";
    None reads config.RETRIEVE_STORE, the deployment's choice. On FAISS the scope is
    the scope's own index plus a filter on the fetched rows; on pgvector it is a
    filter Postgres applies in the same query.
    """
    name = _scope_name(scope)
    allowed = SCOPES[name]
    if folder and folder not in allowed:
        return {"found": False, "reason": f"folder {folder} is outside this caller's scope"}
    folders = frozenset({folder}) if folder else allowed
    if (store or config.RETRIEVE_STORE) == "pgvector":
        return _pgvector_rows(question, k, folders)
    return _faiss_rows(question, k, name, folders)


@tool(description=RETRIEVE_DESCRIPTION)
def retrieve(question: str, k: int = 3, runtime: ToolRuntime[Any] = None) -> list[dict]:
    """The model fills question and k. runtime is the envelope, hidden from the model; it sets the scope."""
    ctx = getattr(runtime, "context", None) if runtime is not None else None
    return retrieve_passages(question, k=k, scope=scope_for(ctx))
