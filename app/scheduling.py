"""Persistent cron execution and explicit output-folder configuration.

Configured folders are a convenience for trusted scripts, not a sandbox. The
scripts still run inside the application container with its existing access.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

DEFAULT_FOLDER_ROOT = "/opt/omniforge/files"


def allowed_folder_roots() -> list[Path]:
    configured = os.environ.get("OMNIFORGE_ALLOWED_FOLDERS", DEFAULT_FOLDER_ROOT)
    roots = []
    for value in configured.split(os.pathsep):
        if value.strip():
            root = Path(value.strip()).expanduser()
            if not root.is_absolute():
                raise ValueError("Allowed folder roots must be absolute paths")
            root = root.resolve()
            if root not in roots:
                roots.append(root)
    return roots


def validate_folder_path(value: str, *, create: bool = False) -> Path:
    """Resolve a configured destination only within explicitly allowed roots."""
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("Choose an output folder")
    raw = Path(value.strip())
    if not raw.is_absolute() or ".." in raw.parts:
        raise ValueError("Output folder must be an absolute path without parent traversal")
    target = raw.resolve()
    roots = allowed_folder_roots()
    if not any(target == root or root in target.parents for root in roots):
        raise ValueError("Output folder must be inside a server-configured allowed folder")
    if target.exists() and not target.is_dir():
        raise ValueError("Output location must be a directory")
    if create:
        target.mkdir(parents=True, exist_ok=True)
        # Recheck after mkdir, including existing symlink parents.
        checked = raw.resolve()
        if checked != target or not any(checked == root or root in checked.parents for root in roots):
            raise ValueError("Output folder changed while preparing execution")
    return target


def list_folders(path: str | None = None) -> dict:
    roots = [str(root) for root in allowed_folder_roots()]
    if path is None or not path.strip():
        return {"roots": roots, "path": None, "folders": []}
    target = validate_folder_path(path)
    if not target.is_dir():
        raise ValueError("Folder does not exist yet; it will be created on first execution")
    folders = []
    try:
        for child in sorted(target.iterdir(), key=lambda item: item.name.casefold()):
            if len(folders) >= 500:
                break
            try:
                if child.is_dir():
                    validate_folder_path(str(child))
                    folders.append({"name": child.name, "path": str(child)})
            except (ValueError, OSError):
                continue
    except OSError as exc:
        raise ValueError("Cannot list this folder; check server permissions") from exc
    return {"roots": roots, "path": str(target), "folders": folders}


def next_run_time(cron: str, zone: str, after: float | None = None) -> float:
    if not isinstance(cron, str) or len(cron) > 128 or len(cron.split()) != 5:
        raise ValueError("Use a five-field cron expression: minute hour day month weekday")
    # Keep the public contract to standard cron ranges, lists, steps and names.
    if not re.fullmatch(r"[a-zA-Z0-9*,/\-\s]+", cron):
        raise ValueError("Cron supports five fields with ranges, lists and steps")
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError("Choose a valid IANA timezone, such as Europe/London or UTC") from exc
    after = time.time() if after is None else after
    # Iterate wall-clock candidates, then convert through zoneinfo ourselves.
    # croniter's timezone-aware offset adjustments can shift a valid 02:00
    # schedule to 03:00 at the autumn transition. Gaps are skipped and repeated
    # times run once, at their first occurrence (fold=0).
    base = datetime.fromtimestamp(after, tz).replace(tzinfo=None)
    try:
        iterator = croniter(cron, base, max_years_between_matches=8)
        for _ in range(3000):
            candidate = iterator.get_next(datetime)
            result = candidate.replace(tzinfo=tz, fold=0).timestamp()
            round_trip = datetime.fromtimestamp(result, tz).replace(tzinfo=None)
            if round_trip == candidate and result > after:
                return result
    except (ValueError, KeyError, OverflowError) as exc:
        raise ValueError("Invalid cron expression or no matching date within eight years") from exc
    raise ValueError("Cron has no valid upcoming local time")


def _iso(value: float | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z") if value is not None else None


def _schedule_key(tool) -> str:
    return hashlib.sha256(json.dumps({"schedule": tool.schedule, "active": tool.is_active}, sort_keys=True).encode()).hexdigest()


class Scheduler:
    """SQLite claims prevent duplicate runs; blocking scripts run in threads."""

    def __init__(self, database, runner=None, *, clock=time.time, poll_interval: float = 5,
                 max_concurrency: int = 4, lease_seconds: float = 120):
        if runner is None:
            from app.runner import run_tool
            runner = run_tool
        self.database = database
        self.runner = runner
        self.clock = clock
        self.poll_interval = max(0.1, min(float(poll_interval), 60))
        self.max_concurrency = max(1, min(int(max_concurrency), 32))
        self.lease_seconds = max(3, float(lease_seconds))
        self._loop_task = None
        self._running: dict[str, asyncio.Task] = {}
        self._stop = asyncio.Event()
        self._ensure_schema()

    def _ensure_schema(self):
        with self.database._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tool_schedule_state (
                    tool_id TEXT PRIMARY KEY REFERENCES tools(id) ON DELETE CASCADE,
                    schedule_key TEXT NOT NULL,
                    next_run REAL,
                    claim_token TEXT,
                    lease_until REAL,
                    last_run REAL,
                    last_status TEXT,
                    last_error TEXT,
                    last_exit_code INTEGER
                );
                CREATE TABLE IF NOT EXISTS tool_schedule_runs (
                    id TEXT PRIMARY KEY,
                    tool_id TEXT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
                    started_at REAL NOT NULL,
                    finished_at REAL,
                    status TEXT NOT NULL,
                    exit_code INTEGER,
                    duration_ms INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_schedule_runs_tool ON tool_schedule_runs(tool_id, started_at DESC);
            """)

    def _sync(self, conn, now: float):
        rows = conn.execute("SELECT * FROM tools").fetchall()
        tools = [self.database._row_to_tool(row) for row in rows]
        for tool in tools:
            state = conn.execute("SELECT * FROM tool_schedule_state WHERE tool_id=?", (tool.id,)).fetchone()
            if tool.schedule is None and state is None:
                continue
            key = _schedule_key(tool)
            if state is None or state["schedule_key"] != key:
                next_at = None
                error = None
                if tool.schedule and tool.schedule.get("enabled") and tool.is_active:
                    try:
                        next_at = next_run_time(tool.schedule["cron"], tool.schedule["timezone"], now)
                    except (ValueError, KeyError):
                        error = "Saved schedule is invalid; update its cron and timezone"
                conn.execute("""INSERT INTO tool_schedule_state(tool_id,schedule_key,next_run,last_error)
                    VALUES (?,?,?,?) ON CONFLICT(tool_id) DO UPDATE SET
                    schedule_key=excluded.schedule_key,next_run=excluded.next_run,last_error=excluded.last_error""",
                    (tool.id, key, next_at, error))
            if state is not None and state["claim_token"] and (state["lease_until"] or 0) <= now:
                # A process exited without completing its lease. Do not replay an
                # uncertain side effect: record interruption and keep next cron.
                conn.execute("UPDATE tool_schedule_runs SET status='interrupted',finished_at=? WHERE id=? AND finished_at IS NULL",
                             (now, state["claim_token"]))
                conn.execute("""UPDATE tool_schedule_state SET claim_token=NULL,lease_until=NULL,
                    last_status='interrupted',last_error='Previous execution was interrupted; check its output before retrying'
                    WHERE tool_id=? AND claim_token=?""", (tool.id, state["claim_token"]))
        return tools

    async def start(self):
        if self._loop_task is None or self._loop_task.done():
            # A TestClient or application reload may use a new event loop.
            self._stop = asyncio.Event()
            self._loop_task = asyncio.create_task(self._loop())

    async def stop(self):
        self._stop.set()
        if self._loop_task is not None:
            await self._loop_task
            self._loop_task = None
        if self._running:
            await asyncio.gather(*list(self._running.values()), return_exceptions=True)

    async def _loop(self):
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception:
                # A transient database error must not permanently stop scheduling.
                import logging
                logging.getLogger(__name__).exception("Scheduler tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass

    async def tick(self, now: float | None = None) -> int:
        now = self.clock() if now is None else now
        self._running = {key: task for key, task in self._running.items() if not task.done()}
        capacity = self.max_concurrency - len(self._running)
        claims = []
        with self.database._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            tools = self._sync(conn, now)
            for tool in tools:
                if capacity <= 0:
                    break
                if tool.id in self._running or not tool.is_active or not tool.schedule or not tool.schedule.get("enabled"):
                    continue
                state = conn.execute("SELECT * FROM tool_schedule_state WHERE tool_id=?", (tool.id,)).fetchone()
                if state is None or state["next_run"] is None or state["next_run"] > now or state["claim_token"]:
                    continue
                token = uuid.uuid4().hex
                try:
                    next_at = next_run_time(tool.schedule["cron"], tool.schedule["timezone"], now)
                except (ValueError, KeyError):
                    continue
                conn.execute("""UPDATE tool_schedule_state SET next_run=?,claim_token=?,lease_until=?,
                    last_run=?,last_status='running',last_error=NULL,last_exit_code=NULL WHERE tool_id=?""",
                    (next_at, token, now + self.lease_seconds, now, tool.id))
                conn.execute("INSERT INTO tool_schedule_runs(id,tool_id,started_at,status) VALUES (?,?,?,'running')",
                             (token, tool.id, now))
                claims.append((tool, token))
                capacity -= 1
        for tool, token in claims:
            self._running[tool.id] = asyncio.create_task(self._execute(tool, token))
        return len(claims)

    async def _heartbeat(self, tool_id: str, token: str, finished: asyncio.Event):
        while not finished.is_set():
            try:
                await asyncio.wait_for(finished.wait(), timeout=self.lease_seconds / 3)
                return
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                # Event-loop shutdown can cancel all Tasks together. The worker
                # Future still runs, so keep its lease alive until _execute says
                # the actual work is finished.
                continue
            try:
                with self.database._connect() as conn:
                    conn.execute("UPDATE tool_schedule_state SET lease_until=? WHERE tool_id=? AND claim_token=?",
                                 (self.clock() + self.lease_seconds, tool_id, token))
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Scheduler lease renewal failed")

    async def _execute(self, claimed_tool, token):
        finished = asyncio.Event()
        heartbeat = asyncio.create_task(self._heartbeat(claimed_tool.id, token, finished))
        status, error, exit_code, duration = "failed", None, None, None
        cancelled = False
        try:
            tool = self.database.get_tool(claimed_tool.name, fresh=True)
            with self.database._connect() as conn:
                state = conn.execute("SELECT claim_token,lease_until FROM tool_schedule_state WHERE tool_id=?", (claimed_tool.id,)).fetchone()
            owns_claim = state and state['claim_token'] == token and (state['lease_until'] or 0) > self.clock()
            if not owns_claim or tool is None or tool.id != claimed_tool.id or not tool.is_active or tool.revision != claimed_tool.revision:
                status = "skipped"
            else:
                tool = claimed_tool
                from app.tool_authoring import validate_arguments
                arguments = tool.schedule.get("arguments", {})
                validate_arguments(arguments, json.loads(tool.json_schema_json or "{}"))
                # Cancelling an asyncio task cannot terminate a script already
                # running in its worker thread. Retain the claim and heartbeat
                # until that worker actually finishes, including during shutdown.
                # Use a Future rather than a child Task so cancellation of all
                # asyncio Tasks cannot discard the worker's completion handle.
                work = asyncio.get_running_loop().run_in_executor(None, self.runner, tool, arguments)
                while True:
                    try:
                        result = await asyncio.shield(work)
                        break
                    except asyncio.CancelledError:
                        cancelled = True
                exit_code, duration = result.exit_code, result.duration_ms
                status = "success" if result.exit_code == 0 and not result.timed_out else "failed"
                if status == "failed":
                    error = "Tool timed out" if result.timed_out else f"Tool exited with code {result.exit_code}; test the tool to inspect its output"
        except Exception:
            error = "Scheduled execution failed; test the tool and check its settings"
        finally:
            finished.set()
            heartbeat.cancel()
            try:
                await asyncio.gather(heartbeat, return_exceptions=True)
            except asyncio.CancelledError:
                cancelled = True
            with self.database._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE tool_schedule_runs SET finished_at=?,status=?,exit_code=?,duration_ms=? WHERE id=?",
                             (self.clock(), status, exit_code, duration, token))
                conn.execute("""UPDATE tool_schedule_state SET claim_token=NULL,lease_until=NULL,
                    last_status=?,last_error=?,last_exit_code=? WHERE tool_id=? AND claim_token=?""",
                    (status, error, exit_code, claimed_tool.id, token))
                conn.execute("""DELETE FROM tool_schedule_runs WHERE tool_id=? AND id NOT IN
                    (SELECT id FROM tool_schedule_runs WHERE tool_id=? ORDER BY started_at DESC LIMIT 50)""",
                    (claimed_tool.id, claimed_tool.id))
        if cancelled:
            raise asyncio.CancelledError

    def get_status(self, tool_id: str) -> dict:
        now = self.clock()
        with self.database._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._sync(conn, now)
            state = conn.execute("SELECT * FROM tool_schedule_state WHERE tool_id=?", (tool_id,)).fetchone()
            history = conn.execute("SELECT * FROM tool_schedule_runs WHERE tool_id=? ORDER BY started_at DESC LIMIT 10", (tool_id,)).fetchall()
        return {"next_run_at": _iso(state["next_run"]) if state else None,
                "last_run_at": _iso(state["last_run"]) if state else None,
                "last_status": state["last_status"] if state else None,
                "last_error": state["last_error"] if state else None,
                "last_exit_code": state["last_exit_code"] if state else None,
                "running": bool(state and state["claim_token"] and (state["lease_until"] or 0) > now),
                "history": [{"started_at": _iso(row["started_at"]), "finished_at": _iso(row["finished_at"]),
                             "status": row["status"], "exit_code": row["exit_code"], "duration_ms": row["duration_ms"]} for row in history]}
