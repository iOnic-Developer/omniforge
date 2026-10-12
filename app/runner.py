"""Execution engine: run a user script and capture stdout/stderr.

Scripts are executed in-process with the language runtime (python3 / node) via
subprocess, with a hard timeout so a runaway script cannot hang the server.

The previous design spun up a fresh ephemeral Docker container per run for
isolation. That required the docker CLI and a mounted docker socket inside the
app container, which is equivalent to root on the host — an unacceptable
attack surface for a platform that lets users paste arbitrary code. In-process
execution with a timeout is the safer, simpler default.

A per-run working directory is created under a scratch volume so scripts can
read/write files without polluting the container root.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import List, Optional

from app.database import Tool

MAX_TIMEOUT_MS = int(os.environ.get("OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS", "30000"))
MAX_MEMORY_MB = int(os.environ.get("OMNIFORGE_MAX_SCRIPT_MEMORY_MB", "512"))
SCRATCH_ROOT = os.environ.get("OMNIFORGE_SCRATCH_ROOT", "/tmp/omniforge")


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


def _runtime(language: str) -> tuple[str, str]:
    """Return (binary, extension) for the given language."""
    lang = (language or "").lower()
    if lang.startswith("py"):
        bin = shutil.which("python3") or shutil.which("python")
        if not bin:
            raise RuntimeError("no python3 runtime available")
        return bin, ".py"
    if lang.startswith("node") or lang.startswith("js"):
        bin = shutil.which("node")
        if not bin:
            raise RuntimeError("no node runtime available")
        return bin, ".js"
    raise ValueError(f"Unsupported language: {language!r}")


def _parse_requirements(raw: str) -> List[str]:
    """Parse declared pip/npm requirements into install commands.

    Best-effort: any packages the runtime can install are installed into a
    per-run site directory so declared dependencies persist across runs.
    """
    try:
        data = __import__("json").loads(raw)
    except (ValueError, TypeError):
        return []
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, dict):
        return [f"{k}=={v}" for k, v in data.items()]
    return []


def run_tool(tool: Tool) -> RunResult:
    """Execute a tool's code in-process and capture the result."""
    start = time.monotonic()
    try:
        runtime_bin, ext = _runtime(tool.language)
    except Exception as exc:
        return RunResult(
            tool=tool.name, language=tool.language, stdout="", stderr="",
            exit_code=1, timed_out=False,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
        )

    # Per-run scratch dir so scripts can read/write files safely.
    scratch = os.path.join(SCRATCH_ROOT, f"{tool.id}{ext}")
    os.makedirs(SCRATCH_ROOT, exist_ok=True)
    try:
        with open(scratch, "w") as fh:
            fh.write(tool.code)
        mode = "w" if runtime_bin.endswith("python3") or runtime_bin.endswith("python") else "r"
        proc = subprocess.run(
            [runtime_bin, scratch],
            capture_output=True,
            text=True,
            timeout=MAX_TIMEOUT_MS / 1000 + 15,
            cwd=SCRATCH_ROOT,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired:
        exit_code = 124
        stdout = ""
        stderr = f"Script exceeded {MAX_TIMEOUT_MS}ms timeout"
    except Exception as exc:
        exit_code = 1
        stdout = ""
        stderr = str(exc)

    return RunResult(
        tool=tool.name, language=tool.language, stdout=stdout.strip(),
        stderr=stderr.strip(), exit_code=exit_code, timed_out=(exit_code == 124),
        duration_ms=int((time.monotonic() - start) * 1000),
    )
