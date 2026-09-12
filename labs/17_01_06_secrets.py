# %% [markdown]
# Secrets and config.py: .env never ships.
#
# When this works, .dockerignore excludes .env, a Python check proves it,
# docker build is tried once, and config.py still finds the model id with
# .env absent. BLOCKED ON DOCKER if the daemon is down.

# %%
from pathlib import Path
import fnmatch
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

dockerignore = root / ".dockerignore"
committed = dockerignore.read_bytes() if dockerignore.is_file() else b""
print("committed_dockerignore_bytes", len(committed))

rules_text = """
.env
.venv
venv
__pycache__
*.pyc
.git
.pytest_cache
renders
dataflow/data/faiss_index
dataflow/data/faiss_index_all
dataflow/data/traces
*.db
"""
dockerignore.write_text(rules_text.strip() + "\n", encoding="utf-8")
print("wrote", dockerignore.as_posix())


def load_rules(text: str) -> list[str]:
    rules = []
    for line in text.splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        rules.append(item)
    return rules


def ignored(rel: str, rules: list[str]) -> bool:
    rel = rel.replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    matched = False
    for rule in rules:
        negate = rule.startswith("!")
        pat = rule[1:] if negate else rule
        pat = pat.rstrip("/")
        hit = (
            rel == pat
            or rel.startswith(pat + "/")
            or fnmatch.fnmatch(rel, pat)
            or fnmatch.fnmatch(rel.split("/")[-1], pat)
        )
        if hit:
            matched = not negate
    return matched


# %%
print("cell", "python_ignore_proof")
rules = load_rules(dockerignore.read_text(encoding="utf-8"))
print("rules", rules)
print("env_excluded", ignored(".env", rules))
print("venv_excluded", ignored(".venv/lib/python.exe", rules))
print("config_py_excluded", ignored("config.py", rules))
print("app_py_excluded", ignored("dataflow/serve/app.py", rules))
print("renders_excluded", ignored("renders/out.mp4", rules))

# %%
print("cell", "docker_build_once")
build = subprocess.run(
    ["docker", "build", "-t", "dataflow-desk:secrets-lab", "."],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
print("docker_build_exit", build.returncode)
if build.stdout:
    print(build.stdout[-2000:])
if build.stderr:
    print(build.stderr[-2000:])
if build.returncode != 0:
    print("BLOCKED ON DOCKER")
    print("docker_error", (build.stderr or build.stdout or "").strip()[:1500])

# %%
print("cell", "config_without_env")
env_path = root / ".env"
saved_env = None
if env_path.is_file():
    saved_env = env_path.read_bytes()
    env_path.unlink()
    print("moved_.env_aside", True)
else:
    print("moved_.env_aside", False)
try:
    import importlib

    import config as config_mod

    importlib.reload(config_mod)
    print("model_id_without_env", config_mod.CHAT_MODEL)
    print("owner", "docs/CURRENCY.md")
finally:
    if saved_env is not None:
        env_path.write_bytes(saved_env)
        print("restored_.env", True)

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
if committed:
    dockerignore.write_bytes(committed)
    print("restored_dockerignore", True)
else:
    print("restored_dockerignore", False)
