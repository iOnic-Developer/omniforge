"""Execution engine: run a user script in an ephemeral container, capture output.

Each tool run spins up a throwaway container (one per language runtime) started
with a CPU quota, a memory cap, a hard timeout, a read-only root filesystem, and
no extra capabilities.

The ephemeral containers run on the Docker engine the CLI talks to, which in this
deployment is a *separate* engine from the one running the OmniForge app itself.
So a bind mount of the app's host filesystem is NOT visible to an ephemeral
container. Instead:

* The script is staged into the shared ``omniforge_scratch`` named volume via a
  small root helper container (the volume is root-owned, so writes must run as
  root, and stdin must be kept open with ``-i``).
* Declared pip/npm dependencies are installed into the shared ``omniforge_lib``
  named volume so they persist across runs and are visible to every ephemeral
  container on that engine.
* The run container mounts both volumes and sets ``PYTHONPATH`` / ``NODE_PATH``.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import List, Optional

from app.database import Tool

RUNTIME_IMAGE = os.environ.get("OMNIFORGE_RUNTIME_IMAGE", "omniforge:latest")
LIB_VOLUME = os.environ.get("OMNIFORGE_LIB_VOLUME", "omniforge_lib")
SCRATCH_VOLUME = os.environ.get("OMNIFORGE_SCRATCH_VOLUME", "omniforge_scratch")
MAX_TIMEOUT_MS = int(os.environ.get("OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS", "30000"))
MAX_MEMORY_MB = int(os.environ.get("OMNIFORGE_MAX_SCRIPT_MEMORY_MB", "512"))


@dataclass
class RunResult:
    tool: str
    language: str
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    duration_ms: int
    error: Optional[str] = None


def _runtime(language: str) -> str:
    lang = (language or "").lower()
    if lang.startswith("py"):
        return "python3"
    if lang.startswith("node") or lang.startswith("js"):
        return "node"
    raise ValueError(f"Unsupported language: {language!r}")


def _docker(args: List[str], input: str | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        ["docker"] + args,
        capture_output=True,
        text=True,
        timeout=180,
        input=input,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _stage_script(tool: Tool) -> None:
    """Write the script into the shared scratch volume (as root, stdin open)."""
    runtime = _runtime(tool.language)
    ext = ".py" if runtime == "python3" else ".js"
    dest = f"/scratch/{tool.id}{ext}"
    proc = subprocess.run(
        ["docker", "run", "--rm", "-i", "--user", "root", "-v",
         f"{SCRATCH_VOLUME}:/scratch", RUNTIME_IMAGE,
         "sh", "-c", f"cat > '{dest}'"],
        input=tool.code,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "script staging failed")


def _install_requirements(language: str, requirements: List[str]) -> None:
    """Install declared pip/npm requirements into the persistent lib volume.

    Packages are installed into the lib volume so they persist across runs and
    are visible to every ephemeral container on that engine.

    The requirements file is written into the lib volume via a root ``cat >``
    helper: bind-mounting a host file into the read-only image's filesystem
    silently creates a directory instead of a file, so the content is piped
    in through stdin.
    """
    if not requirements:
        return
    runtime = _runtime(language)
    if runtime == "python3":
        script = (
            "mkdir -p /lib/py3/site-packages && "
            "cat > /lib/py3/site-packages/_reqs.txt && "
            "pip install --no-cache-dir --target /lib/py3/site-packages"
            " -r /lib/py3/site-packages/_reqs.txt"
        )
        _docker(
            [
                "run", "--rm", "-i", "--user", "root",
                "-v", f"{LIB_VOLUME}:/lib:rw", RUNTIME_IMAGE,
                "sh", "-c", script,
            ],
            input="\n".join(requirements) + "\n",
        )
    else:
        # npm needs a package.json; build one from the requirements list.
        deps = {}
        for item in requirements:
            if "==" in item:
                name, ver = item.split("==", 1)
                deps[name] = ver
            else:
                deps[item] = "*"
        pkg = json.dumps({"name": "omniforge-deps", "dependencies": deps})
        script = (
            "mkdir -p /lib/node_modules && "
            "cat > /lib/node_modules/package.json && "
            "cd /lib/node_modules && npm install --prefix /lib/node_modules"
        )
        _docker(
            [
                "run", "--rm", "-i", "--user", "root",
                "-v", f"{LIB_VOLUME}:/lib:rw", RUNTIME_IMAGE,
                "sh", "-c", script,
            ],
            input=pkg,
        )


def _parse_requirements(raw: str) -> List[str]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, dict):
        return [f"{k}=={v}" for k, v in data.items()]
    return []


def run_tool(tool: Tool) -> RunResult:
    """Execute a tool's code in an ephemeral container and capture the result."""
    start = time.monotonic()
    runtime = _runtime(tool.language)
    ext = ".py" if runtime == "python3" else ".js"
    dest = f"/scratch/{tool.id}{ext}"

    # Stage the script into the shared scratch volume.
    try:
        _stage_script(tool)
    except Exception as exc:
        return RunResult(
            tool=tool.name, language=tool.language, stdout="", stderr="",
            exit_code=1, timed_out=False,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=f"Script staging failed: {exc}",
        )

    # Install declared requirements (best-effort).
    try:
        _install_requirements(tool.language, _parse_requirements(tool.requirements_json))
    except Exception as exc:
        return RunResult(
            tool=tool.name, language=tool.language, stdout="", stderr="",
            exit_code=1, timed_out=False,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=f"Dependency install failed: {exc}",
        )

    docker_args = [
        "run", "--rm",
        "--name", f"omniforge_run_{tool.id}",
        "--cpus", "1",
        "--memory", f"{MAX_MEMORY_MB}m",
        "--read-only",
        "--cap-drop", "ALL",
        "--pids-limit", "256",
        "-v", f"{SCRATCH_VOLUME}:/scratch:ro",
        "-v", f"{LIB_VOLUME}:/lib:ro",
    ]
    if runtime == "python3":
        # Environment variables must precede the image name.
        docker_args += ["-e", "PYTHONPATH=/lib/py3/site-packages",
                        RUNTIME_IMAGE, "python3", dest]
    else:
        docker_args += ["-e", "NODE_PATH=/lib/node_modules",
                        RUNTIME_IMAGE, "node", dest]

    timed_out = False
    try:
        proc = subprocess.run(
            ["docker"] + docker_args,
            capture_output=True,
            text=True,
            timeout=MAX_TIMEOUT_MS / 1000 + 15,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired:
        timed_out = True
        exit_code = 124
        stdout = ""
        stderr = f"Script exceeded {MAX_TIMEOUT_MS}ms timeout"

    return RunResult(
        tool=tool.name, language=tool.language, stdout=stdout.strip(),
        stderr=stderr.strip(), exit_code=exit_code, timed_out=timed_out,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
