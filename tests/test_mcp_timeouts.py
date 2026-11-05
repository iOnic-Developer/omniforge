"""The authoring contract exposes persisted, enforced script deadlines."""
import asyncio
import json
import tempfile
import time
import unittest
from unittest.mock import patch

from app import main, mcp_server, runner, tool_authoring
from app.database import Database


class MCPTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Database(self.temp.name + '/tools.db')
        for module in (main, mcp_server, tool_authoring):
            self.enterContext(patch.object(module, 'db', self.db))
        self.enterContext(patch.object(runner, 'SCRATCH_ROOT', self.temp.name + '/runs'))
        self.handler = mcp_server.MCPHandler()

    def create(self, **changes):
        arguments = {'name': 'deadline_tool', 'code': 'print("done")'}
        arguments.update(changes)
        return self.handler.call_tool('omniforge_create_tool', arguments)

    def test_llm_can_discover_and_set_45_seconds(self):
        tools = self.handler.list_tools()['tools']
        schema = next(t for t in tools if t['name'] == 'omniforge_create_tool')['inputSchema']
        timeout = schema['properties']['timeout_seconds']
        self.assertEqual(timeout['default'], 120)
        instructions = self.handler.call_tool('omniforge_instructions', {})
        contract = json.loads(instructions['content'][0]['text'])['contract']
        self.assertIn('120', contract['timeout_seconds'])
        self.assertIn('45', contract['timeout_seconds'])
        self.assertIn('timeout_seconds', self.handler.initialize('2025-06-18', {})['instructions'])
        created = self.create(timeout_seconds=45)
        self.assertFalse(created['isError'], created)
        self.assertEqual(self.db.get_tool('deadline_tool', fresh=True).timeout_seconds, 45)
        listed = asyncio.run(main.api_list_tools())['tools'][0]
        self.assertEqual(listed.timeout_seconds, 45)

    def test_omitted_creation_timeout_defaults_to_two_minutes(self):
        result = self.create()
        self.assertFalse(result['isError'], result)
        self.assertEqual(self.db.get_tool('deadline_tool', fresh=True).timeout_seconds, 120)

    def test_invalid_timeouts_are_not_saved(self):
        for value in (0, -1, 3601, True, '45', 1.5, None):
            with self.subTest(timeout=value):
                result = self.create(timeout_seconds=value)
                self.assertTrue(result['isError'])
                self.assertIsNone(self.db.get_tool('deadline_tool', fresh=True))

    def test_mcp_execution_reports_a_real_deadline_as_an_error(self):
        self.assertFalse(self.create(code='import time\ntime.sleep(4)\nprint("too late")',
                                     timeout_seconds=1)['isError'])
        started = time.monotonic()
        result = self.handler.call_tool('deadline_tool', {})
        duration = time.monotonic() - started
        self.assertTrue(result['isError'])
        text = '\n'.join(block['text'] for block in result['content'])
        self.assertIn('[timeout]', text)
        self.assertNotIn('too late', text)
        self.assertLess(duration, 3, 'The previous extra 15 seconds must not be added')
