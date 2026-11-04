"""Persistent MCP client credentials, sessions, and per-connection tool choices.

Only token hashes are stored. Display IDs are deliberately not credentials.
Tool choices use stable identities so a rename does not restore hidden access.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone


SESSION_TTL_SECONDS = 24 * 60 * 60


def _stamp(value: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if value is None else value, timezone.utc).isoformat()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def tool_key(tool) -> str:
    return 'tool:' + tool.id


def builtin_key(name: str) -> str:
    return 'builtin:' + name


class ConnectionStore:
    def __init__(self, database):
        self.database = database
        with self.database._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS mcp_connections (
                    id TEXT PRIMARY KEY,
                    client_name TEXT NOT NULL,
                    client_version TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL,
                    credential_hash TEXT UNIQUE,
                    disabled_keys_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS mcp_sessions (
                    token_hash TEXT PRIMARY KEY,
                    connection_id TEXT NOT NULL,
                    principal_hash TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    ended INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_mcp_sessions_connection
                    ON mcp_sessions(connection_id);
            ''')

    def catalogue(self, builtins: list[dict]) -> dict[str, dict]:
        result = {t['name']: {'name': t['name'], 'description': t.get('description', ''),
                              'is_active': True, 'key': builtin_key(t['name'])}
                  for t in builtins}
        result.update({t.name: {'name': t.name, 'description': t.description,
                               'is_active': t.is_active, 'key': tool_key(t)}
                       for t in self.database.get_tool_list() if t.name not in result})
        return result

    @staticmethod
    def _public(row, catalogue: dict[str, dict], connected: bool = False) -> dict:
        disabled = set(json.loads(row['disabled_keys_json']))
        return {
            'id': row['id'], 'client_name': row['client_name'],
            'client_version': row['client_version'], 'kind': row['kind'],
            'created_at': row['created_at'], 'last_seen_at': row['last_seen_at'],
            'connected': connected and row['revoked_at'] is None,
            'enabled': row['revoked_at'] is None, 'revoked_at': row['revoked_at'],
            'disabled_tools': [name for name, tool in catalogue.items() if tool['key'] in disabled],
            'tool_count': sum(t['is_active'] and t['key'] not in disabled for t in catalogue.values()),
        }

    def list_connections(self, builtins: list[dict]) -> dict:
        catalogue = self.catalogue(builtins)
        with self.database._connect() as conn:
            rows = conn.execute('SELECT * FROM mcp_connections ORDER BY created_at DESC').fetchall()
            active = {r[0] for r in conn.execute(
                'SELECT DISTINCT connection_id FROM mcp_sessions WHERE ended=0 AND last_seen>?',
                (time.time() - SESSION_TTL_SECONDS,))}
        return {'connections': [self._public(r, catalogue, r['id'] in active) for r in rows],
                'tools': [{k: v for k, v in t.items() if k != 'key'} for t in catalogue.values()]}

    def create_named(self, name: str, builtins: list[dict]) -> tuple[dict, str]:
        token = 'ofc_' + secrets.token_urlsafe(32)
        connection_id = uuid.uuid4().hex
        with self.database._connect() as conn:
            conn.execute('''INSERT INTO mcp_connections
                (id,client_name,kind,credential_hash,created_at) VALUES (?,?,?,?,?)''',
                (connection_id, name, 'named', _digest(token), _stamp()))
            row = conn.execute('SELECT * FROM mcp_connections WHERE id=?', (connection_id,)).fetchone()
        return self._public(row, self.catalogue(builtins)), token

    def authenticate_named(self, token: str) -> str | None:
        with self.database._connect() as conn:
            row = conn.execute('''SELECT id FROM mcp_connections
                WHERE credential_hash=? AND revoked_at IS NULL AND kind='named' ''', (_digest(token),)).fetchone()
        return row['id'] if row else None

    def start_session(self, principal: str, client_info: dict,
                      connection_id: str | None = None) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        now = time.time()
        name = client_info.get('name', 'Unnamed client')
        version = client_info.get('version', '')
        if not isinstance(name, str) or not isinstance(version, str) or len(name) > 120 or len(version) > 80:
            raise ValueError('clientInfo name/version must be strings of at most 120/80 characters')
        with self.database._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            # Bound expired transient session records while preserving named policies.
            cutoff = now - SESSION_TTL_SECONDS
            conn.execute('UPDATE mcp_sessions SET ended=1 WHERE last_seen<?', (cutoff,))
            conn.execute('''DELETE FROM mcp_connections WHERE kind='session' AND id NOT IN
                (SELECT connection_id FROM mcp_sessions WHERE last_seen>?)''', (now - 7 * SESSION_TTL_SECONDS,))
            conn.execute('DELETE FROM mcp_sessions WHERE last_seen<?', (now - 7 * SESSION_TTL_SECONDS,))
            if connection_id is None:
                connection_id = uuid.uuid4().hex
                conn.execute('''INSERT INTO mcp_connections
                    (id,client_name,client_version,kind,created_at,last_seen_at) VALUES (?,?,?,?,?,?)''',
                    (connection_id, name or 'Unnamed client', version, 'session', _stamp(now), _stamp(now)))
            else:
                row = conn.execute('SELECT * FROM mcp_connections WHERE id=? AND revoked_at IS NULL',
                                   (connection_id,)).fetchone()
                if not row:
                    raise ValueError('Connection is disconnected')
                conn.execute('UPDATE mcp_connections SET client_version=?,last_seen_at=? WHERE id=?',
                             (version, _stamp(now), connection_id))
            conn.execute('INSERT INTO mcp_sessions VALUES (?,?,?,?,?,0)',
                         (_digest(token), connection_id, _digest(principal), now, now))
        return token, connection_id

    def resolve_session(self, token: str, principal: str) -> str | None:
        now = time.time()
        with self.database._connect() as conn:
            row = conn.execute('''SELECT s.connection_id,s.last_seen FROM mcp_sessions s
                JOIN mcp_connections c ON c.id=s.connection_id
                WHERE s.token_hash=? AND s.principal_hash=? AND s.ended=0
                AND s.last_seen>? AND c.revoked_at IS NULL''',
                (_digest(token), _digest(principal), now - SESSION_TTL_SECONDS)).fetchone()
            if not row:
                return None
            if now - row['last_seen'] >= 30:
                conn.execute('UPDATE mcp_sessions SET last_seen=? WHERE token_hash=?', (now, _digest(token)))
                conn.execute('UPDATE mcp_connections SET last_seen_at=? WHERE id=?',
                             (_stamp(now), row['connection_id']))
        return row['connection_id']

    def end_session(self, token: str, principal: str) -> bool:
        if self.resolve_session(token, principal) is None:
            return False
        with self.database._connect() as conn:
            conn.execute('UPDATE mcp_sessions SET ended=1 WHERE token_hash=?', (_digest(token),))
        return True

    def disabled_keys(self, connection_id: str) -> set[str]:
        with self.database._connect() as conn:
            row = conn.execute('SELECT disabled_keys_json FROM mcp_connections WHERE id=? AND revoked_at IS NULL',
                               (connection_id,)).fetchone()
        if row is None:
            raise ValueError('Connection is disconnected')
        return set(json.loads(row['disabled_keys_json']))

    def update_policy(self, connection_id: str, disabled_names: list[str], builtins: list[dict]) -> dict | None:
        catalogue = self.catalogue(builtins)
        if any(name not in catalogue for name in disabled_names):
            raise ValueError('Unknown tool in connection settings; refresh the tool list')
        keys = sorted({catalogue[name]['key'] for name in disabled_names})
        with self.database._connect() as conn:
            cur = conn.execute('UPDATE mcp_connections SET disabled_keys_json=? WHERE id=? AND revoked_at IS NULL',
                               (json.dumps(keys), connection_id))
            if not cur.rowcount:
                return None
            row = conn.execute('SELECT * FROM mcp_connections WHERE id=?', (connection_id,)).fetchone()
            active = conn.execute('SELECT 1 FROM mcp_sessions WHERE connection_id=? AND ended=0 AND last_seen>?',
                                  (connection_id, time.time() - SESSION_TTL_SECONDS)).fetchone()
        return self._public(row, catalogue, bool(active))

    def disconnect(self, connection_id: str) -> bool:
        with self.database._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            cur = conn.execute('UPDATE mcp_connections SET revoked_at=? WHERE id=? AND revoked_at IS NULL',
                               (_stamp(), connection_id))
            conn.execute('UPDATE mcp_sessions SET ended=1 WHERE connection_id=?', (connection_id,))
        return bool(cur.rowcount)
