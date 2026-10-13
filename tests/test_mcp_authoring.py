import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app import main, mcp_server, runner, tool_authoring
from app.database import Database, DuplicateToolError
from app.tool_authoring import ToolIn


class AuthoringTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.db = Database(self.scratch.name + '/test.db')
        for module in (main, mcp_server, tool_authoring):
            patcher = patch.object(module, 'db', self.db)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(runner, 'SCRATCH_ROOT', self.scratch.name + '/runs')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.handler = mcp_server.MCPHandler()

    def call(self, name, arguments=None):
        return self.handler.call_tool(name, {} if arguments is None else arguments)

    def create(self, **changes):
        args = {'name': 'sample', 'description': 'Test script',
                'code': 'print("hello")', 'language': 'python3'}
        args.update(changes)
        return self.call('omniforge_create_tool', args)

    def text(self, result):
        self.assertEqual(result['content'][0]['type'], 'text')
        return result['content'][0]['text']

    def test_builtins_discoverable_with_empty_database(self):
        self.assertEqual(self.db.get_tool_list(), [])
        tools = self.handler.list_tools()['tools']
        self.assertEqual({t['name'] for t in tools}, tool_authoring.BUILTIN_NAMES)
        for tool in tools:
            self.assertEqual(tool['inputSchema']['type'], 'object')

    def test_instructions_contract_and_no_credentials(self):
        sentinel = 'synthetic-not-a-real-credential'
        with patch.dict(os.environ, {'OMNIFORGE_API_KEY': sentinel, 'SECRET_TEST': sentinel}), patch.object(main, 'API_KEY', sentinel):
            result = self.call('omniforge_instructions')
            exposed = json.dumps(self.handler.list_tools()) + self.text(result)
        self.assertFalse(result['isError'])
        self.assertNotIn(sentinel, exposed)
        data = json.loads(self.text(result))
        self.assertEqual(len(data['examples']), 2)
        self.assertIn('NOT implemented', data['contract']['requirements'])
        self.assertIn('stdin', data['contract']['inputs'])
        self.assertIn('Streamable HTTP', ' '.join(data['limitations']))
        self.assertIn('inherit', ' '.join(data['limitations']))

    def test_instructions_examples_create_and_execute(self):
        data = json.loads(self.text(self.call('omniforge_instructions')))
        for example in data['examples']:
            with self.subTest(language=example['language']):
                created = self.call('omniforge_create_tool', example)
                self.assertFalse(created['isError'], self.text(created))
                result = self.call(example['name'], {'name': 'David'})
                self.assertFalse(result['isError'], self.text(result))
                self.assertEqual(json.loads(self.text(result))['message'], 'Hello David')

    def test_create_saves_only_and_invalidates_discovery_cache(self):
        self.handler.list_tools()  # prime the empty cache
        with patch.object(mcp_server, 'run_tool') as execute:
            result = self.create()
            execute.assert_not_called()
        self.assertFalse(result['isError'], self.text(result))
        data = json.loads(self.text(result))
        self.assertFalse(data['executed'])
        self.assertEqual(self.db.get_tool('sample').code, 'print("hello")')
        self.assertEqual(len(self.handler.list_tools()['tools']), 3)
        self.assertFalse(Path(runner.SCRATCH_ROOT).exists())

    def test_duplicate_create_does_not_overwrite_even_when_inactive(self):
        self.assertFalse(self.create(is_active=False)['isError'])
        result = self.create(code='raise Exception("replacement")')
        self.assertTrue(result['isError'])
        self.assertIn('already exists', self.text(result))
        self.assertEqual(self.db.get_tool('sample').code, 'print("hello")')
        self.assertEqual(len(self.db.get_tool_list()), 1)
        self.assertTrue(self.call('sample')['isError'])
        self.assertEqual(len(self.handler.list_tools()['tools']), 2)

    def test_create_validation(self):
        cases = [
            {'name': '../bad'}, {'name': 'x' * 64}, {'name': 5}, {'name': ''},
            {'language': 'shell'}, {'language': 5}, {'description': []},
            {'code': ''}, {'code': '  \n'}, {'code': 5}, {'code': 'print(1)\x00'},
            {'inputSchema': []}, {'inputSchema': {'type': 'array'}},
            {'inputSchema': {'properties': {}}},
            {'inputSchema': {'type': 'object', 'properties': {'x': {'type': 'bogus'}}}},
            {'inputSchema': {'type': 'object', 'required': 'x'}},
            {'inputSchema': {'type': 'object', '$schema': 'https://json-schema.org/draft-07/schema'}},
            {'inputSchema': {'type': 'object', 'properties': {'x': {'$ref': 'https://example.invalid/schema'}}}},
            {'inputSchema': {'type': 'object', '$ref': 'file:///etc/passwd'}},
            {'inputSchema': {'type': 'object', '$dynamicRef': 'https://example.invalid/schema'}},
            {'is_active': 'true'}, {'requirements': 'requests'}, {'requirements': [5]},
            {'unknown_field': True},
        ]
        for changes in cases:
            with self.subTest(changes=changes), patch.object(mcp_server, 'run_tool') as execute:
                result = self.create(**changes)
                self.assertTrue(result['isError'], result)
                execute.assert_not_called()
        self.assertEqual(self.db.get_tool_list(), [])

    def test_create_missing_required_fields(self):
        for args in ({}, {'name': 'sample'}, {'code': 'print(1)'}):
            with self.subTest(args=args):
                self.assertTrue(self.call('omniforge_create_tool', args)['isError'])

    def test_nonempty_requirements_explicitly_rejected(self):
        result = self.create(requirements=['requests'])
        self.assertTrue(result['isError'])
        self.assertIn('dynamic dependency installation is not implemented', self.text(result))
        self.assertEqual(self.db.get_tool_list(), [])

    def test_invalid_argument_container_types_and_names(self):
        for name in ('omniforge_instructions', 'omniforge_create_tool', 'missing'):
            for value in (None, [], 'string', 5, True):
                with self.subTest(name=name, value=value):
                    self.assertTrue(self.handler.call_tool(name, value)['isError'])
        for name in (None, [], {}, 5, ''):
            self.assertTrue(self.handler.call_tool(name, {})['isError'])
        self.assertTrue(self.call('omniforge_instructions', {'extra': True})['isError'])

    def test_reserved_names_rejected_in_both_paths(self):
        for name in tool_authoring.BUILTIN_NAMES:
            self.assertTrue(self.create(name=name)['isError'])
            with self.assertRaises(ValidationError):
                ToolIn(name=name, code='print(1)')
            for api in (main.api_run_tool, main.api_delete_tool, main.api_toggle_tool):
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(api(name))
                self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(self.db.get_tool_list(), [])

    def test_legacy_rows_cannot_shadow_builtins(self):
        self.create()
        source = self.db.get_tool('sample')
        for name in tool_authoring.BUILTIN_NAMES:
            # Simulate a legacy row without passing through authoring validation.
            self.db.upsert(replace(source, id=self.db.next_id(), name=name))
        names = [t['name'] for t in self.handler.list_tools()['tools']]
        self.assertEqual(names.count('omniforge_instructions'), 1)
        self.assertEqual(names.count('omniforge_create_tool'), 1)
        with patch.object(mcp_server, 'run_tool') as execute:
            result = self.call('omniforge_instructions')
            execute.assert_not_called()
        self.assertIn('workflow', json.loads(self.text(result)))

    def test_dashboard_duplicate_and_rename_collision(self):
        one = ToolIn(name='one', code='print(1)')
        two = ToolIn(name='two', code='print(2)')
        asyncio.run(main.api_create_tool(one))
        asyncio.run(main.api_create_tool(two))
        for operation in (main.api_create_tool(one), main.api_update_tool('two', one)):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(operation)
            self.assertEqual(raised.exception.status_code, 409)
        asyncio.run(main.api_update_tool('one', ToolIn(name='renamed', code='print(3)')))
        self.assertIsNone(self.db.get_tool('one'))
        self.assertEqual(self.db.get_tool('renamed').code, 'print(3)')

    def test_dashboard_uses_shared_metadata_validation(self):
        for changes in ({'name': '../bad'}, {'language': 'bash'}, {'code': ''},
                        {'json_schema': {'type': 'array'}}):
            args = {'name': 'valid', 'code': 'print(1)'}
            args.update(changes)
            with self.assertRaises(ValidationError):
                ToolIn(**args)
        body = ToolIn(name='stored_requirements', code='print(1)', requirements=['requests'])
        asyncio.run(main.api_create_tool(body))
        self.assertEqual(json.loads(self.db.get_tool(body.name).requirements_json), ['requests'])

    def test_duplicate_guard_across_database_connections(self):
        self.create()
        source = self.db.get_tool('sample')
        databases = [Database(self.db.path), Database(self.db.path)]
        barrier = threading.Barrier(2)

        def insert(index):
            barrier.wait()
            try:
                databases[index].upsert(replace(source, id=str(index), name='concurrent'), create_only=True)
                return 'created'
            except DuplicateToolError:
                return 'duplicate'

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(pool.map(insert, range(2)), ['created', 'duplicate'])

    def test_legacy_duplicate_rows_preserved_without_migration(self):
        self.create()
        with self.db._connect() as conn:
            conn.execute('INSERT INTO tools SELECT ?, name, description, language, code, requirements_json, json_schema_json, is_active, created_at, updated_at FROM tools WHERE name = ?', ('legacy', 'sample'))
        reopened = Database(self.db.path)
        self.assertEqual(len(reopened.get_tool_list()), 2)
        with self.assertRaises(DuplicateToolError):
            reopened.upsert(replace(reopened.get_tool('sample'), id='new'), create_only=True)
        self.assertEqual(len(reopened.get_tool_list()), 2)

    def test_json_stdin_forwarding_python_and_node(self):
        args = {'text': 'quotes " and $(not-a-command)\n雪', 'nested': {'items': [1, True, None]}}
        scripts = {
            'python': 'import json, sys\nprint(json.dumps(json.load(sys.stdin)))',
            'javascript': 'const fs = require("node:fs"); console.log(JSON.stringify(JSON.parse(fs.readFileSync(0, "utf8"))));',
        }
        for language, code in scripts.items():
            with self.subTest(language=language):
                name = 'echo_' + language
                created = self.create(name=name, language=language, code=code, inputSchema={'type': 'object'})
                self.assertFalse(created['isError'])
                result = self.call(name, args)
                self.assertFalse(result['isError'], self.text(result))
                self.assertEqual(json.loads(self.text(result)), args)
                # API runs supply an empty object even without an explicit input.
                ui = asyncio.run(main.api_run_tool(name))
                self.assertEqual(json.loads(ui['stdout']), {})

    def test_argument_schema_checked_before_execution(self):
        schema = {'type': 'object', 'properties': {'count': {'type': 'integer', 'minimum': 1}},
                  'required': ['count'], 'additionalProperties': False}
        self.create(inputSchema=schema)
        with patch.object(mcp_server, 'run_tool') as execute:
            for args in ({}, {'count': '1'}, {'count': True}, {'count': 0}, {'count': 1, 'extra': True}):
                self.assertTrue(self.call('sample', args)['isError'])
            execute.assert_not_called()
        result = self.call('sample', {'count': 2})
        self.assertFalse(result['isError'])

    def test_no_input_schema_rejects_extra_inputs(self):
        self.create()
        with patch.object(mcp_server, 'run_tool') as execute:
            self.assertTrue(self.call('sample', {'unexpected': True})['isError'])
            execute.assert_not_called()
        self.assertFalse(self.call('sample')['isError'])

    def test_local_schema_references(self):
        schema = {'type': 'object', '$defs': {'value': {'type': 'string'}},
                  'properties': {'value': {'$ref': '#/$defs/value'}}}
        self.assertFalse(self.create(inputSchema=schema)['isError'])
        self.assertFalse(self.call('sample', {'value': 'ok'})['isError'])
        self.assertTrue(self.call('sample', {'value': 5})['isError'])
        schema['properties']['value']['$ref'] = '#/$defs/missing'
        self.assertFalse(self.create(name='unresolved', inputSchema=schema)['isError'])
        self.assertTrue(self.call('unresolved', {'value': 'x'})['isError'])

    def test_runtime_failure_and_runtime_lookup_error(self):
        self.create(code='import sys\nprint("failure details", file=sys.stderr)\nsys.exit(7)')
        result = self.call('sample')
        self.assertTrue(result['isError'])
        self.assertIn('[stderr] failure details', self.text(result))
        self.assertIn('[exit 7]', self.text(result))
        with patch.object(runner, '_runtime', side_effect=RuntimeError('no runtime available')):
            result = self.call('sample')
        self.assertTrue(result['isError'])
        self.assertIn('no runtime available', self.text(result))

    def test_timeout_is_reported_as_tool_error(self):
        self.create()
        with patch.object(runner.subprocess, 'run', side_effect=subprocess.TimeoutExpired('python', 1)):
            result = self.call('sample')
        self.assertTrue(result['isError'])
        self.assertIn('[timeout]', self.text(result))

    def test_invalid_syntax_saved_but_only_fails_on_execution(self):
        self.assertFalse(self.create(code='this is not valid Python !!!')['isError'])
        result = self.call('sample')
        self.assertTrue(result['isError'])
        self.assertIn('SyntaxError', self.text(result))

    def test_validation_errors_do_not_echo_submitted_secrets(self):
        sentinel = 'synthetic-submitted-secret'
        cases = ({'name': '../' + sentinel}, {'language': sentinel}, {'code': sentinel + '\x00'},
                 {'inputSchema': {'type': 'object', 'required': sentinel}},
                 {'unexpected': sentinel})
        for changes in cases:
            result = self.create(**changes)
            self.assertTrue(result['isError'])
            self.assertNotIn(sentinel, self.text(result))

    def test_hot_updates_and_toggle_discovery(self):
        self.create()
        self.handler.list_tools()
        asyncio.run(main.api_update_tool('sample', ToolIn(name='updated', code='print(2)')))
        names = [t['name'] for t in self.handler.list_tools()['tools']]
        self.assertNotIn('sample', names)
        self.assertIn('updated', names)
        asyncio.run(main.api_toggle_tool('updated'))
        self.assertEqual(len(self.handler.list_tools()['tools']), 2)
        self.assertTrue(self.call('updated')['isError'])
        asyncio.run(main.api_toggle_tool('updated'))
        self.assertEqual(len(self.handler.list_tools()['tools']), 3)

    def test_rpc_envelopes_and_invalid_params(self):
        for value in (None, [], 'string'):
            rpc = asyncio.run(main._handle_rpc({'method': 'tools/call', 'id': 1, 'params': value}))
            self.assertEqual(rpc['error']['code'], -32602)
        rpc = asyncio.run(main._handle_rpc({'method': 'tools/call', 'id': 2, 'params': {
            'name': 'omniforge_create_tool', 'arguments': []}}))
        self.assertEqual(rpc['id'], 2)
        self.assertTrue(rpc['result']['isError'])
        listed = asyncio.run(main._handle_rpc({'method': 'tools/list', 'id': 3}))
        self.assertEqual(len(listed['result']['tools']), 2)
        capabilities = self.handler.initialize('2024-11-05', {})['capabilities']
        self.assertFalse(capabilities['tools']['listChanged'])

    def test_post_auth_applies_to_builtins(self):
        request = Request({'type': 'http', 'headers': []})
        payload = {'method': 'tools/call', 'id': 1, 'params': {'name': 'omniforge_create_tool', 'arguments': {'name': 'blocked', 'code': 'print(1)'}}}
        with patch.object(main, 'API_KEY', 'synthetic-auth-test'):
            response = asyncio.run(main.mcp_endpoint(payload, request))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.db.get_tool_list(), [])


if __name__ == '__main__':
    unittest.main()
