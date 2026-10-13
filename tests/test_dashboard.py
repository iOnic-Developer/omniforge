import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

scratch = tempfile.TemporaryDirectory()
os.environ['OMNIFORGE_DB_PATH'] = scratch.name + '/test.db'
os.environ['OMNIFORGE_SCRATCH_ROOT'] = scratch.name + '/runs'
from app import main


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

    def test_dashboard_controls(self):
        page = Path('app/templates/dashboard.html').read_text()
        self.assertIn('id="configBtn"', page)
        self.assertIn('id="exampleBtn"', page)
        self.assertIn("/run`, { method: 'POST' }", page)
        self.assertIn('pre.textContent = message', page)
        self.assertNotIn('out.innerHTML', page)


if __name__ == '__main__':
    unittest.main()
