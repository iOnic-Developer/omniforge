"""SQLite-backed storage for tool metadata.

Writes use SQLite transactions. Reads happen per
request with a short in-memory cache that is invalidated on any write, giving
hot-reload without a container restart.
"""

from __future__ import annotations

import os
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

DB_PATH = os.environ.get("OMNIFORGE_DB_PATH", "/opt/omniforge/data/omniforge.db")
CACHE_TTL = int(os.environ.get("OMNIFORGE_CACHE_TTL_MS", "5000"))


@dataclass
class Tool:
    id: str
    name: str
    description: str
    language: str
    code: str
    requirements_json: str
    json_schema_json: str
    is_active: bool
    created_at: str
    updated_at: str
    revision: str = field(init=False)

    def __post_init__(self) -> None:
        # Content identity, not a second-resolution timestamp. No migration required.
        values = [self.id, self.name, self.description, self.language, self.code,
                  self.requirements_json, self.json_schema_json, self.is_active]
        self.revision = hashlib.sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()


class DuplicateToolError(ValueError):
    """A different tool already uses the requested name."""


class ToolConflictError(ValueError):
    """A conditional write targets a deleted or changed tool."""


class Database:
    def __init__(self, path: str = DB_PATH) -> None:
        self.path = path
        self._cache: dict[str, tuple[list[Tool], float]] = {}
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tools (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    language TEXT NOT NULL,
                    code TEXT NOT NULL,
                    requirements_json TEXT NOT NULL DEFAULT '[]',
                    json_schema_json TEXT NOT NULL DEFAULT '{}',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tools_name ON tools(name)")

    def _invalidate(self) -> None:
        self._cache.clear()

    @staticmethod
    def _row_to_tool(row: sqlite3.Row) -> Tool:
        return Tool(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            language=row["language"],
            code=row["code"],
            requirements_json=row["requirements_json"],
            json_schema_json=row["json_schema_json"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _fetch_all(self) -> list[Tool]:
        with self._lock:
            cached = self._cache.get("all")
            if cached and time.monotonic() - cached[1] < CACHE_TTL / 1000:
                return cached[0]
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM tools ORDER BY updated_at DESC"
                ).fetchall()
            tools = [self._row_to_tool(r) for r in rows]
            self._cache["all"] = (tools, time.monotonic())
            return tools

    def get_tool(self, name: str, fresh: bool = False) -> Optional[Tool]:
        with self._lock:
            cached = self._cache.get("all")
            if not fresh and cached and time.monotonic() - cached[1] < CACHE_TTL / 1000:
                for t in cached[0]:
                    if t.name == name:
                        return t
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM tools WHERE name = ?", (name,)
                ).fetchone()
            return self._row_to_tool(row) if row else None

    def get_tool_list(self) -> list[Tool]:
        return self._fetch_all()

    def upsert(self, tool: Tool, create_only: bool = False, expected_revision: str | None = None) -> Tool:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._lock:
            with self._connect() as conn:
                # Serialize check+write across connections without migrating or
                # deleting legacy duplicate rows in existing databases.
                conn.execute("BEGIN IMMEDIATE")
                if expected_revision is not None:
                    row = conn.execute("SELECT * FROM tools WHERE id = ?", (tool.id,)).fetchone()
                    if row is None or self._row_to_tool(row).revision != expected_revision:
                        raise ToolConflictError("Tool changed in another tab or client; reload before changing it")
                duplicate = conn.execute(
                    "SELECT id FROM tools WHERE name = ? AND (id != ? OR ?) LIMIT 1",
                    (tool.name, tool.id, int(create_only)),
                ).fetchone()
                if duplicate:
                    raise DuplicateToolError('Tool name already exists; choose another name or edit it in the dashboard')
                conn.execute(
                    """
                    INSERT INTO tools
                    (id, name, description, language, code, requirements_json,
                     json_schema_json, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        description=excluded.description,
                        language=excluded.language,
                        code=excluded.code,
                        requirements_json=excluded.requirements_json,
                        json_schema_json=excluded.json_schema_json,
                        is_active=excluded.is_active,
                        created_at=excluded.created_at,
                        updated_at=excluded.updated_at
                    """,
                    (
                        tool.id,
                        tool.name,
                        tool.description,
                        tool.language,
                        tool.code,
                        tool.requirements_json,
                        tool.json_schema_json,
                        int(tool.is_active),
                        tool.created_at or now,
                        now,
                    ),
                )
                conn.commit()
            self._invalidate()
            return tool

    def delete(self, name: str, expected_revision: str | None = None) -> bool:
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if expected_revision is not None:
                    rows = conn.execute("SELECT * FROM tools WHERE name = ?", (name,)).fetchall()
                    if len(rows) != 1 or self._row_to_tool(rows[0]).revision != expected_revision:
                        raise ToolConflictError("Tool changed in another tab or client; reload before deleting it")
                cur = conn.execute(
                    "DELETE FROM tools WHERE name = ?", (name,)
                )
                conn.commit()
            self._invalidate()
            return cur.rowcount > 0

    def toggle(self, name: str, expected_revision: str | None = None) -> Tool | None:
        """Atomically flip one identity, never a stale replacement with the same name."""
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT * FROM tools WHERE name = ?", (name,)).fetchone()
                if row is None:
                    return None
                tool = self._row_to_tool(row)
                if expected_revision is not None and tool.revision != expected_revision:
                    raise ToolConflictError("Tool changed in another tab or client; reload before toggling it")
                conn.execute("UPDATE tools SET is_active = ?, updated_at = ? WHERE id = ?",
                             (int(not tool.is_active), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), tool.id))
                updated = conn.execute("SELECT * FROM tools WHERE id = ?", (tool.id,)).fetchone()
                conn.commit()
            self._invalidate()
            return self._row_to_tool(updated)

    def activate(self, name: str, active: bool) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE tools SET is_active = ?, updated_at = ? WHERE name = ?",
                    (int(active), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), name),
                )
                conn.commit()
            self._invalidate()

    def next_id(self) -> str:
        return uuid.uuid4().hex[:12]


db = Database()
