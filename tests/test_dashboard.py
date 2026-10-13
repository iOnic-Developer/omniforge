import asyncio
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

scratch = tempfile.TemporaryDirectory()
os.environ['OMNIFORGE_DB_PATH'] = scratch.name + '/test.db'
os.environ['OMNIFORGE_SCRATCH_ROOT'] = scratch.name + '/runs'
from app import main, mcp_server, tool_authoring
from app.database import Database


class DashboardTests(unittest.TestCase):
    def test_config_never_exposes_key(self):
        with patch.object(main, 'API_KEY', 'test-secret-not-for-display'):
            config = asyncio.run(main.api_config())
        self.assertTrue(config['auth_enabled'])
        self.assertNotIn('test-secret-not-for-display', json.dumps(config))
        self.assertFalse(config['connection_tracking'])
        with patch.object(main, 'API_KEY', ''):
            self.assertFalse(asyncio.run(main.api_config())['auth_enabled'])

    def test_example_runs(self):
        body = main.ToolIn(name='example_hello', code='import json\nprint(json.dumps({"message": "Hello from OmniForge!", "ok": True}))')
        asyncio.run(main.api_create_tool(body))
        result = asyncio.run(main.api_run_tool('example_hello'))
        self.assertEqual(result['exit_code'], 0)
        self.assertTrue(json.loads(result['stdout'])['ok'])

    def test_http_routes(self):
        methods = {route.path: route.methods for route in main.app.routes}
        self.assertEqual(methods['/api/tools/{name}/run'], {'POST'})
        self.assertEqual(methods['/api/config'], {'GET'})

    def test_toggle_hides_discovery_not_dashboard_and_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(directory + '/toggle.db')
            with patch.object(main, 'db', db), patch.object(tool_authoring, 'db', db), patch.object(mcp_server, 'db', db):
                asyncio.run(main.api_create_tool(main.ToolIn(name='toggle_test', code='print("ok")')))
                handler = mcp_server.MCPHandler()
                self.assertIn('toggle_test', {t['name'] for t in handler.list_tools()['tools']})
                asyncio.run(main.api_toggle_tool('toggle_test'))
                self.assertNotIn('toggle_test', {t['name'] for t in handler.list_tools()['tools']})
                listed = asyncio.run(main.api_list_tools())['tools']
                self.assertEqual(len(listed), 1)
                self.assertFalse(listed[0].is_active)
                self.assertEqual(listed[0].code, 'print("ok")')
                self.assertTrue(tool_authoring.BUILTIN_NAMES.issubset({t['name'] for t in handler.list_tools()['tools']}))
                asyncio.run(main.api_toggle_tool('toggle_test'))
                self.assertIn('toggle_test', {t['name'] for t in handler.list_tools()['tools']})

    def test_four_examples_validate_and_create_without_install(self):
        page = Path('app/templates/dashboard.html').read_text()
        examples = json.loads(re.search(r'const EXAMPLES = (\{.*?\});', page, re.S).group(1))
        self.assertEqual(len(examples), 4)
        with tempfile.TemporaryDirectory() as directory:
            db = Database(directory + '/examples.db')
            with patch.object(main, 'db', db), patch.object(tool_authoring, 'db', db), patch.object(main, 'run_tool') as run:
                for example in examples.values():
                    asyncio.run(main.api_create_tool(main.ToolIn(**example)))
                run.assert_not_called()
                self.assertEqual(len(db.get_tool_list()), 4)
                for example in examples.values():
                    with self.assertRaises(main.HTTPException) as error:
                        asyncio.run(main.api_create_tool(main.ToolIn(**example)))
                    self.assertEqual(error.exception.status_code, 409)
                self.assertEqual(len(db.get_tool_list()), 4)

    def test_dashboard_controls(self):
        page = Path('app/templates/dashboard.html').read_text()
        self.assertIn('id="configBtn"', page)
        self.assertIn('id="exampleBtn"', page)
        self.assertIn("/run`, { method: 'POST' }", page)
        self.assertIn('pre.textContent = message', page)
        self.assertNotIn('out.innerHTML', page)
        for control in ('collapseLeft', 'collapseRight', 'helpBtn', 'installExamplesBtn', 'lineNumbers'):
            self.assertIn('id="' + control + '"', page)
        for target in ('toolName', 'toolLanguage', 'toolDescription', 'toolCode', 'toolRequirements'):
            self.assertIn('for="' + target + '"', page)
        self.assertIn('grid-template-columns:var(--left) minmax(0,1fr) var(--right)', page)
        self.assertIn('grid-template-columns:minmax(0,1fr)', page)
        self.assertIn('min-height:44px', page)
        self.assertIn('button:focus-visible', page)
        self.assertIn('wrap="off"', page)
        self.assertNotIn('🛠', page)


if __name__ == '__main__':
    unittest.main()
