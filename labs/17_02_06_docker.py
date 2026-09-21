# %% [markdown]
# Dockerfile and Compose for DataFlow.
#
# When this works, docker compose config validates the file, docker build
# and compose up are tried once, BLOCKED ON DOCKER if the daemon is down,
# Dockerfile.broken plants the WORKDIR miss, and docker_request.json is
# written only from a real container run.

# %%
from pathlib import Path
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

dockerfile = root / "Dockerfile"
print("cue", "Dockerfile verbatim")
print("dockerfile_lines", len(dockerfile.read_text(encoding="utf-8").splitlines()))
print("--- Dockerfile ---")
print(dockerfile.read_text(encoding="utf-8"))
print("--- end ---")

broken = root / "Dockerfile.broken"
print("broken_workdir")
for line in broken.read_text(encoding="utf-8").splitlines():
    if line.startswith("WORKDIR"):
        print("planted", line)
        print("why", "WORKDIR /wrong means the copied app is not the cwd, so uvicorn cannot import dataflow.serve.app and /health never comes up")

runs = root / "deploy" / "runs"
runs.mkdir(parents=True, exist_ok=True)
blocked_path = runs / "docker_request.BLOCKED.md"
json_path = runs / "docker_request.json"

# %%
print("cell", "compose_config")
config = subprocess.run(
    ["docker", "compose", "--profile", "ship", "config"],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
print("compose_config_exit", config.returncode)
if config.stdout:
    print(config.stdout[:3000])
if config.stderr:
    print(config.stderr[:1500])

# %%
print("cell", "docker_build_and_up")
print("A first build installs the whole course into the image and can take 15 minutes; later builds reuse it.")
build = subprocess.run(
    ["docker", "build", "-t", "dataflow-desk:lab", "."],
    cwd=str(root),
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
print("docker_build_exit", build.returncode)
build_err = (build.stderr or build.stdout or "").strip()
if build.stderr:
    print(build.stderr[-2000:])
if build.returncode != 0:
    print("BLOCKED ON DOCKER")
    print("docker_error", build_err[:2000])
    blocked_path.write_text(
        "BLOCKED ON DOCKER\n\n" + build_err[:4000] + "\n",
        encoding="utf-8",
    )
    print("wrote", blocked_path.as_posix())
    if json_path.is_file():
        json_path.unlink()
        print("removed stale docker_request.json")
else:
    up = subprocess.run(
        ["docker", "compose", "--profile", "ship", "up", "-d", "dataflow"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print("compose_up_exit", up.returncode)
    if up.returncode != 0:
        print("BLOCKED ON DOCKER")
        err = (up.stderr or up.stdout or "").strip()
        print("docker_error", err[:2000])
        blocked_path.write_text(
            "BLOCKED ON DOCKER\n\n" + err[:4000] + "\n",
            encoding="utf-8",
        )
        print("wrote", blocked_path.as_posix())
    else:
        import time
        import urllib.request

        base = "http://127.0.0.1:8000"
        health_body = None
        print("waiting for container health ", end="", flush=True)
        for _ in range(60):
            try:
                with urllib.request.urlopen(base + "/health", timeout=5) as resp:
                    health_body = json.loads(resp.read().decode("utf-8"))
                    break
            except Exception:
                print(".", end="", flush=True)
                time.sleep(2)
        print()
        if health_body is None:
            print("container health never answered at", base + "/health", "within 120 seconds")
            print("not writing docker_request.json from a container that is not healthy")
            print("Check docker compose logs dataflow, then run this lab again.")
        else:
            print("container_health", health_body)
            request = {"ticket": "Where is order DF-1002?"}
            req = urllib.request.Request(
                base + "/run",
                data=json.dumps(request).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    status = resp.status
                    reply = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                print("container_post_error", type(exc).__name__ + ":", exc)
                print("The container is healthy but POST /run failed: is Ollama running on this machine?")
            else:
                print("container_post_status", status)
                print("container_reply", reply)
                json_path.write_text(
                    json.dumps(
                        {"url": base + "/run", "request": request, "status": status, "response": reply},
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                print("wrote", json_path.as_posix(), "from the real container POST")
                if blocked_path.is_file():
                    blocked_path.unlink()

# %% [markdown]
# restore the committed copy so the repo stays clean; delete this cell to keep yours

# %%
print("cell", "restore")
print("Dockerfile and compose were not rewritten")
print("BLOCKED.md is gitignored runtime output")
