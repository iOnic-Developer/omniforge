"""Execution engine: run a user script and capture stdout/stderr.

Scripts run as subprocesses in the shared application container. This is NOT
an isolation boundary: trusted scripts can access the application environment,
network and writable data. Each tool has an exact script timeout, defaulting to
120 seconds; expiry kills its Linux process group. Dependency preparation has
separate bounded waits. Per-script memory limits are not implemented.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Optional

from app.database import Tool
from app.dependencies import ensure_dependencies
from app.scheduling import validate_folder_path

MAX_MEMORY_MB = int(os.environ.get("OMNIFORGE_MAX_SCRIPT_MEMORY_MB", "512"))
SCRATCH_ROOT = os.environ.get("OMNIFORGE_SCRATCH_ROOT", "/tmp/omniforge")
OUTPUT_DRAIN_TIMEOUT_SECONDS = 1


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


def _kill_process_group(process: subprocess.Popen) -> None:
    """The child is its session/group leader; ordinary descendants share it."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # The complete group has already exited.


def _text(value) -> str:
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''


def _drain_after_kill(process: subprocess.Popen) -> tuple[str, str]:
    """Do not wait indefinitely for pipes held by an escaped/detached child."""
    try:
        return process.communicate(timeout=OUTPUT_DRAIN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        try:
            process.wait(timeout=OUTPUT_DRAIN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        return _text(exc.output), _text(exc.stderr)


def run_tool(tool: Tool, arguments: dict | None = None) -> RunResult:
    """Execute saved code; JSON stdin defaults to {} for dashboard runs."""
    start = time.monotonic()
    try:
        timeout_seconds = tool.timeout_seconds
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
            raise ValueError('Tool timeout_seconds must be an integer from 1 to 3600')
        if os.name != 'posix':
            raise RuntimeError('Script execution requires Linux/POSIX process-group support')
        input_json = json.dumps({} if arguments is None else arguments, allow_nan=False)
        runtime_bin, ext = _runtime(tool.language)
        packages = ensure_dependencies(tool, runtime_bin)
        environment = os.environ.copy()
        # A tool without this feature must not inherit another tool's setting.
        environment.pop('OMNIFORGE_OUTPUT_DIR', None)
        output_folder = None
        if tool.folder_access and tool.folder_access.get('enabled'):
            output_folder = validate_folder_path(tool.folder_access.get('path', ''), create=True)
            environment['OMNIFORGE_OUTPUT_DIR'] = str(output_folder)
        if packages is not None:
            key = 'PYTHONPATH' if ext == '.py' else 'NODE_PATH'
            environment[key] = str(packages) + (os.pathsep + environment[key] if environment.get(key) else '')
    except Exception as exc:
        return RunResult(
            tool=tool.name, language=tool.language, stdout="", stderr=str(exc),
            exit_code=1, timed_out=False,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(exc),
        )

    # Every call gets its own script path; concurrent manual/scheduled calls
    # cannot overwrite each other's source. This is still a shared container.
    process = None
    timed_out = False
    stdout, stderr, exit_code = '', '', 1
    try:
        os.makedirs(SCRATCH_ROOT, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"{tool.id}-", dir=SCRATCH_ROOT) as scratch_dir:
            scratch = os.path.join(scratch_dir, f"tool{ext}")
            with open(scratch, "w", encoding="utf-8") as fh:
                fh.write(tool.code)
            process = subprocess.Popen(
                [runtime_bin, scratch],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace',
                cwd=str(output_folder) if output_folder else scratch_dir,
                env=environment, start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(input=input_json, timeout=timeout_seconds)
                exit_code = process.returncode
                # A tool owns its ordinary descendants even when they redirect
                # every pipe. Do not leave fire-and-forget work running after
                # the parent has returned a result and its scratch is removed.
                _kill_process_group(process)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_process_group(process)
                stdout, stderr = _drain_after_kill(process)
                exit_code = 124
                stderr = (stderr + '\n' if stderr else '') + f'Script exceeded {timeout_seconds}s timeout; process group killed'
    except Exception as exc:
        exit_code = 1
        stderr = str(exc)
        if process is not None:
            try:
                _kill_process_group(process)
                stdout, _ = _drain_after_kill(process)
            except OSError as cleanup_error:
                stderr += f'; process cleanup failed: {cleanup_error}'
    finally:
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()

    return RunResult(
        tool=tool.name, language=tool.language, stdout=stdout.strip(),
        stderr=stderr.strip(), exit_code=exit_code, timed_out=timed_out,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
