"""Opt-in real installs: OMNIFORGE_LIVE_INSTALL_TESTS=1, writable lib root."""
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app import dependencies, main, mcp_server, runner, tool_authoring
from app.database import Database
from app.tool_authoring import ToolIn


@unittest.skipUnless(os.environ.get('OMNIFORGE_LIVE_INSTALL_TESTS') == '1', 'Opt-in live package installation')
class LiveExampleTests(unittest.TestCase):
    def test_exact_four_dashboard_examples_and_cache(self):
        html = Path('/app/app/templates/dashboard.html').read_text()
        examples = json.loads(re.search(r'const EXAMPLES = (\{.*?\});', html, re.S).group(1))
        self.assertEqual(set(examples), {'python_basic', 'node_basic', 'python_packages', 'node_packages'})
        with tempfile.TemporaryDirectory(dir=dependencies.LIB_ROOT, prefix='live-test-') as lib, tempfile.TemporaryDirectory() as scratch:
            db = Database(scratch + '/test.db')
            with patch.object(dependencies, 'LIB_ROOT', lib), patch.object(runner, 'SCRATCH_ROOT', scratch + '/runs'), patch.object(main, 'db', db), patch.object(tool_authoring, 'db', db), patch.object(mcp_server, 'db', db):
                real_run = subprocess.run
                installer_calls = []
                def record(command, **kwargs):
                    if '--target' in command or '--prefix' in command:
                        installer_calls.append(command)
                    return real_run(command, **kwargs)
                with patch.object(dependencies.subprocess, 'run', side_effect=record):
                    for key, example in examples.items():
                        with self.subTest(example=key):
                            asyncio.run(main.api_create_tool(ToolIn(**example)))
                            installer_calls.clear()
                            result = asyncio.run(main.api_run_tool(example['name']))
                            self.assertEqual(result['exit_code'], 0, result)
                            value = json.loads(result['stdout'])
                            self.assertTrue(value['ok'])
                            self.assertEqual(len(installer_calls), 1 if example['requirements'] else 0)
                            if key == 'node_packages':
                                self.assertEqual(value['numbers'], [1, 2, 3])
                            if key == 'python_packages':
                                self.assertEqual(value['url'], 'https://example.com/?hello=David')
                            installer_calls.clear()
                            cached = mcp_server.MCPHandler().call_tool(example['name'], {})
                            self.assertFalse(cached['isError'], cached)
                            # MCP intentionally appends stderr diagnostics to stdout.
                            # Successful dependencies may emit warnings; assert the JSON
                            # stdout contract without pretending the whole MCP text is JSON.
                            cached_text = cached['content'][0]['text']
                            self.assertTrue(json.loads(cached_text.split('\n[stderr] ', 1)[0])['ok'])
                            self.assertEqual(installer_calls, [])
                            print(f'LIVE PASS {key}: first dashboard run + cached MCP run', flush=True)
                self.assertEqual(len(list(Path(lib).rglob('.complete'))), 2)
                self.assertFalse(list(Path(lib).rglob('.install-*')))
