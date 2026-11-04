"""HTTP lifecycle, credential isolation, and persistent connection tool choices."""
import asyncio
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main, mcp_server, tool_authoring
from app.connections import ConnectionStore
from app.database import Database
from app.scheduling import Scheduler
from app.tool_authoring import ToolIn


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Database(self.temp.name + '/connections.db')
        self.store = ConnectionStore(self.db)
        for module in (main, mcp_server, tool_authoring):
            self.enterContext(patch.object(module, 'db', self.db))
        self.enterContext(patch.object(main, 'connections', self.store))
        self.enterContext(patch.object(main, 'scheduler', Scheduler(self.db)))
        self.enterContext(patch.object(main, 'API_KEY', 'synthetic-management-key'))
        self.admin = {'Authorization': 'Bearer synthetic-management-key'}
        self.http = self.enterContext(TestClient(main.app))
        self.create_tool('first')
        self.create_tool('second')

    def create_tool(self, name):
        return tool_authoring.save_tool(ToolIn(name=name, code='print("hello")'))

    def named(self, name='OpenAI'):
        response = self.http.post('/api/connections', headers=self.admin, json={'client_name': name})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        return body['connection']['id'], {'Authorization': 'Bearer ' + body['token']}, body['token']

    def initialize(self, headers=None, name='test-client'):
        response = self.http.post('/mcp', headers=headers or self.admin, json={
            'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
                'protocolVersion': '2025-06-18', 'capabilities': {},
                'clientInfo': {'name': name, 'version': '1'}}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('mcp-session-id', response.headers)
        return {**(headers or self.admin), 'Mcp-Session-Id': response.headers['mcp-session-id'],
                'MCP-Protocol-Version': response.json()['result']['protocolVersion']}

    def rpc(self, headers, method='tools/list', params=None):
        return self.http.post('/mcp', headers=headers, json={
            'jsonrpc': '2.0', 'id': 2, 'method': method, 'params': params or {}})

    def names(self, headers):
        response = self.rpc(headers)
        self.assertEqual(response.status_code, 200, response.text)
        return {t['name'] for t in response.json()['result']['tools']}

    def policy(self, connection_id, names):
        response = self.http.put('/api/connections/' + connection_id,
                                  headers=self.admin, json={'disabled_tools': names})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['connection']

    def test_new_connections_and_new_tools_are_all_visible_by_default(self):
        _, credential, _ = self.named()
        headers = self.initialize(credential)
        self.assertIn('first', self.names(headers))
        self.assertIn('omniforge_create_tool', self.names(headers))
        self.create_tool('new_after_connection')
        self.assertIn('new_after_connection', self.names(headers))

    def test_visibility_filters_discovery_and_execution_and_persists_on_reconnect(self):
        connection_id, credential, _ = self.named()
        headers = self.initialize(credential)
        self.policy(connection_id, ['first', 'omniforge_create_tool'])
        self.assertNotIn('first', self.names(headers))
        self.assertNotIn('omniforge_create_tool', self.names(headers))
        with patch.object(mcp_server, 'run_tool') as run:
            for name in ('first', 'omniforge_create_tool'):
                response = self.rpc(headers, 'tools/call', {'name': name, 'arguments': {}})
                self.assertTrue(response.json()['result']['isError'])
            run.assert_not_called()
        reconnect = self.initialize(credential)
        self.assertNotIn('first', self.names(reconnect))
        self.assertIn('second', self.names(reconnect))
        self.policy(connection_id, [])
        self.assertIn('first', self.names(headers))

    def test_tool_rename_keeps_disabled_identity_and_other_clients_unaffected(self):
        connection_id, credential, _ = self.named()
        headers = self.initialize(credential)
        other = self.initialize()
        self.policy(connection_id, ['first'])
        first = self.db.get_tool('first', fresh=True)
        self.db.upsert(replace(first, name='renamed'), expected_revision=first.revision)
        self.assertNotIn('renamed', self.names(headers))
        self.assertIn('renamed', self.names(other))
        listed = self.http.get('/api/connections', headers=self.admin).json()['connections']
        profile = next(c for c in listed if c['id'] == connection_id)
        self.assertEqual(profile['disabled_tools'], ['renamed'])

    def test_disconnect_revokes_all_sessions_and_named_credential(self):
        connection_id, credential, _ = self.named()
        first, second = self.initialize(credential), self.initialize(credential)
        self.assertEqual(self.http.delete('/api/connections/' + connection_id, headers=self.admin).status_code, 200)
        for headers in (first, second):
            self.assertEqual(self.rpc(headers).status_code, 401)
        # The same bearer token cannot initialize again with a fresh session.
        response = self.http.post('/mcp', headers=credential,
                                  json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'})
        self.assertEqual(response.status_code, 401)
        profile = next(c for c in self.http.get('/api/connections', headers=self.admin).json()['connections']
                       if c['id'] == connection_id)
        self.assertFalse(profile['enabled'])
        self.assertFalse(profile['connected'])

    def test_transient_disconnect_returns_404_and_never_falls_back(self):
        session = self.initialize()
        profile = self.http.get('/api/connections', headers=self.admin).json()['connections'][0]
        self.http.delete('/api/connections/' + profile['id'], headers=self.admin)
        self.assertEqual(self.rpc(session).status_code, 404)
        self.assertEqual(self.rpc(self.admin).status_code, 400)

    def test_session_cannot_be_borrowed_with_another_credential(self):
        _, one, _ = self.named('one')
        _, two, _ = self.named('two')
        session = self.initialize(one)
        self.assertEqual(self.rpc({**session, **two}).status_code, 404)
        self.assertEqual(self.rpc({**session, **self.admin}).status_code, 404)

    def test_session_notification_and_delete_transport(self):
        session = self.initialize()
        response = self.http.post('/mcp', headers=session,
                                  json={'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.content, b'')
        self.assertEqual(self.http.get('/mcp', headers=session).status_code, 405)
        self.assertEqual(self.http.delete('/mcp', headers=session).status_code, 204)
        self.assertEqual(self.rpc(session).status_code, 404)

    def test_management_api_requires_master_not_named_credential(self):
        _, credential, _ = self.named()
        for headers in ({}, credential, {'Authorization': 'Bearer wrong'}):
            self.assertEqual(self.http.get('/api/connections', headers=headers).status_code, 401)
            self.assertEqual(self.http.post('/api/connections', headers=headers,
                                           json={'client_name': 'unauthorized'}).status_code, 401)

    def test_tokens_are_hashed_and_never_listed(self):
        _, credential, token = self.named()
        session = self.initialize(credential)
        serialized = self.http.get('/api/connections', headers=self.admin).text
        self.assertNotIn(token, serialized)
        self.assertNotIn(session['Mcp-Session-Id'], serialized)
        with self.db._connect() as conn:
            stored = str([tuple(r) for r in conn.execute('SELECT * FROM mcp_connections')])
            stored += str([tuple(r) for r in conn.execute('SELECT * FROM mcp_sessions')])
        self.assertNotIn(token, stored)
        self.assertNotIn(session['Mcp-Session-Id'], stored)
        self.assertNotIn('synthetic-management-key', stored)

    def test_policy_survives_store_reload_and_unknown_tools_rejected(self):
        connection_id, credential, _ = self.named()
        self.policy(connection_id, ['first'])
        with patch.object(main, 'connections', ConnectionStore(self.db)):
            self.assertNotIn('first', self.names(self.initialize(credential)))
        response = self.http.put('/api/connections/' + connection_id, headers=self.admin,
                                  json={'disabled_tools': ['missing']})
        self.assertEqual(response.status_code, 400)

    def test_legacy_reserved_row_does_not_override_builtin_policy_identity(self):
        original = self.db.get_tool('first', fresh=True)
        self.db.upsert(replace(original, name='omniforge_create_tool'))
        connection_id, credential, _ = self.named()
        self.policy(connection_id, ['omniforge_create_tool'])
        headers = self.initialize(credential)
        self.assertNotIn('omniforge_create_tool', self.names(headers))
        response = self.rpc(headers, 'tools/call', {'name': 'omniforge_create_tool',
                                                  'arguments': {'name': 'blocked', 'code': 'print(1)'}})
        self.assertTrue(response.json()['result']['isError'])
        self.assertIsNone(self.db.get_tool('blocked', fresh=True))

    def test_untrusted_origin_and_unknown_protocol_are_rejected(self):
        session = self.initialize()
        self.assertEqual(self.rpc({**session, 'Origin': 'https://untrusted.invalid'}).status_code, 403)
        self.assertEqual(self.rpc({**session, 'MCP-Protocol-Version': 'unknown'}).status_code, 400)

    def test_revoked_named_token_cannot_fall_through_when_shared_key_is_unset(self):
        connection_id, credential, _ = self.named()
        self.store.disconnect(connection_id)
        with patch.object(main, 'API_KEY', ''):
            self.assertEqual(self.rpc(credential).status_code, 401)

    def test_client_metadata_is_bounded_and_returned_as_data(self):
        self.initialize(name='<script>alert(1)</script>')
        data = self.http.get('/api/connections', headers=self.admin).json()
        self.assertEqual(data['connections'][0]['client_name'], '<script>alert(1)</script>')
        self.assertFalse(any('token' in k for k in data['connections'][0]))
