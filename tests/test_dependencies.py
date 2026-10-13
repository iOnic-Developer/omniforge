from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app import dependencies, runner
from app.database import Tool
from app.tool_authoring import ToolIn


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'lib'
        for module, key, value in ((dependencies, 'LIB_ROOT', str(self.root)),
                                   (runner, 'SCRATCH_ROOT', self.temp.name + '/scratch')):
            p = patch.object(module, key, value)
            p.start()
            self.addCleanup(p.stop)
        self.tool = Tool('a', 'sample', '', 'python3', 'print(42)', '["requests"]', '{}', True, '', '')

    def fake_success(self, command, **kwargs):
        target = Path(command[command.index('--target') + 1]) if '--target' in command else Path(command[command.index('--prefix') + 1]) / 'node_modules'
        target.mkdir()
        return subprocess.CompletedProcess(command, 0)

    def test_cache_hash_tool_language_and_order(self):
        with patch.object(dependencies.subprocess, 'run', side_effect=self.fake_success) as install:
            first = dependencies.ensure_dependencies(self.tool, '/usr/bin/python3')
            self.assertEqual(first, dependencies.ensure_dependencies(self.tool, '/usr/bin/python3'))
            self.assertEqual(install.call_count, 1)
            variants = [replace(self.tool, id='b'), replace(self.tool, requirements_json='["requests==2.32.5"]'),
                        replace(self.tool, language='node', requirements_json='["requests"]')]
            for tool in variants:
                self.assertNotEqual(first, dependencies.ensure_dependencies(tool, '/usr/bin/python3'))
            both = replace(self.tool, requirements_json='["requests", "urllib3"]')
            ordered = dependencies.ensure_dependencies(both, '/usr/bin/python3')
            self.assertEqual(ordered, dependencies.ensure_dependencies(replace(both, requirements_json='["urllib3", "requests", "requests"]'), '/usr/bin/python3'))
        self.assertEqual(len(list(self.root.rglob('.complete'))), 5)
        self.assertFalse(list(self.root.rglob('.install-*')))

    def test_failed_install_no_execute_no_marker_clean_own_stage_only(self):
        unrelated = self.root / 'user-files'
        unrelated.mkdir(parents=True)
        (unrelated / 'keep').write_text('keep')
        sentinel = 'synthetic-api-secret'
        def fail(command, **kwargs):
            kwargs['stderr'].write(('x' * 5000 + sentinel + ' https://user:password@example.invalid').encode())
            return subprocess.CompletedProcess(command, 1)
        with patch.dict(os.environ, {'OMNIFORGE_API_KEY': sentinel}), patch.object(dependencies.subprocess, 'run', side_effect=fail) as execute:
            result = runner.run_tool(self.tool)
        self.assertEqual(execute.call_count, 1)  # Installer only, never the script.
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Dependency installation failed', result.stderr)
        self.assertNotIn(sentinel, result.stderr)
        self.assertNotIn('password', result.stderr)
        self.assertLess(len(result.stderr), 3200)
        self.assertFalse(list(self.root.rglob('.complete')))
        self.assertFalse(list(self.root.rglob('.install-*')))
        self.assertTrue((unrelated / 'keep').is_file())

    def test_timeout_no_execute_no_marker_then_retry(self):
        with patch.object(dependencies.subprocess, 'run', side_effect=subprocess.TimeoutExpired('pip', 120)) as execute:
            result = runner.run_tool(self.tool)
        self.assertEqual(execute.call_count, 1)
        self.assertIn('timed out after 120s', result.stderr)
        self.assertFalse(list(self.root.rglob('.complete')))
        self.assertFalse(list(self.root.rglob('.install-*')))
        with patch.object(dependencies.subprocess, 'run', side_effect=self.fake_success):
            self.assertTrue(dependencies.ensure_dependencies(self.tool, '/usr/bin/python3').is_dir())

    def test_lock_serializes_install_and_bounded_wait(self):
        def slow(command, **kwargs):
            time.sleep(0.2)
            return self.fake_success(command, **kwargs)
        with patch.object(dependencies.subprocess, 'run', side_effect=slow) as install, ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(lambda _: dependencies.ensure_dependencies(self.tool, '/usr/bin/python3'), range(2)))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(install.call_count, 1)
        with patch.object(dependencies.fcntl, 'flock', side_effect=BlockingIOError), patch.object(dependencies, 'LOCK_TIMEOUT', 0):
            with self.assertRaisesRegex(dependencies.DependencyError, 'lock wait timed out'):
                dependencies.ensure_dependencies(self.tool, '/usr/bin/python3')

    def test_minimal_environment_official_installer_flags_and_runtime_environment(self):
        for language, requirements, key in [('python3', '["requests"]', 'PYTHONPATH'), ('node', '["lodash"]', 'NODE_PATH')]:
            tool = replace(self.tool, language=language, requirements_json=requirements)
            with patch.dict(os.environ, {'OMNIFORGE_API_KEY': 'sentinel', 'PIP_INDEX_URL': 'https://private.invalid', 'NPM_CONFIG_REGISTRY': 'https://private.invalid', key: '/existing'}), patch.object(dependencies.subprocess, 'run', side_effect=self.fake_success) as install:
                directory = dependencies.ensure_dependencies(tool, '/usr/bin/python3')
                command = install.call_args.args[0]
                env = install.call_args.kwargs['env']
                self.assertNotIn('OMNIFORGE_API_KEY', env)
                self.assertNotIn('PIP_INDEX_URL', env)
                self.assertNotIn('NPM_CONFIG_REGISTRY', env)
                self.assertNotIn(key, env)
                self.assertTrue(Path(env['TMPDIR']).is_relative_to(self.root))
                self.assertIn('.install-', env['TMPDIR'])
                self.assertEqual(install.call_args.kwargs['timeout'], 120)
                if language == 'python3':
                    for flag in ('--target', '--only-binary=:all:', '--no-cache-dir', '--disable-pip-version-check', 'https://pypi.org/simple'):
                        self.assertIn(flag, command)
                else:
                    for flag in ('--prefix', '--ignore-scripts', '--no-audit', '--no-fund', '--cache', 'https://registry.npmjs.org'):
                        self.assertIn(flag, command)
                with patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '42', '')) as script:
                    result = runner.run_tool(tool)
                    runtime_env = script.call_args.kwargs['env']
                self.assertEqual(result.exit_code, 0)
                self.assertEqual(runtime_env['OMNIFORGE_API_KEY'], 'sentinel')
                self.assertEqual(runtime_env[key], str(directory) + os.pathsep + '/existing')

    def test_valid_names_pins_and_malicious_lines_rejected_by_authoring_and_execution(self):
        for language, values in [('python3', ['requests', 'requests==2.32.5', 'pillow==11.0.0rc1']),
                                 ('node', ['lodash', 'lodash@4.17.21', '@scope/name', '@scope/name@1.2.3-beta.1'])]:
            ToolIn(name='valid', language=language, code='print(1)', requirements=values)
        malicious = ['--index-url=x', '-r requirements.txt', 'git+https://example.com/x', 'https://example.com/x.whl',
                     '../x', '/tmp/x', 'foo;touch /tmp/x', 'foo\nbar', 'foo $(id)', 'foo\x00', 'foo@npm:lodash',
                     'foo.tar.gz#x', 'foo>=1', 'foo[extra]', 'foo;python_version>"3"']
        for language in ('python3', 'node'):
            for requirement in malicious:
                with self.subTest(language=language, requirement=requirement):
                    with self.assertRaises(ValidationError):
                        ToolIn(name='valid', language=language, code='print(1)', requirements=[requirement])
                    with patch.object(dependencies.subprocess, 'run') as execute:
                        result = runner.run_tool(replace(self.tool, language=language, requirements_json=json.dumps([requirement])))
                        self.assertNotEqual(result.exit_code, 0)
                        execute.assert_not_called()
        for requirement in ('foo@latest', 'foo@^1.2.3', 'foo@01.2.3', 'foo@1.2.3-01', 'node_modules@1.0.0'):
            with self.assertRaises(dependencies.DependencyError):
                dependencies.validate_requirements([requirement], 'node')
        for raw in ('not json', '{"requests":"1"}', '[5]'):
            result = runner.run_tool(replace(self.tool, requirements_json=raw))
            self.assertNotEqual(result.exit_code, 0)


    def test_existing_incomplete_directory_is_preserved(self):
        with patch.object(dependencies.subprocess, 'run', side_effect=self.fake_success):
            packages = dependencies.ensure_dependencies(self.tool, '/usr/bin/python3')
        (packages.parent / '.complete').unlink()
        (packages / 'user-file').write_text('keep')
        with patch.object(dependencies.subprocess, 'run') as install:
            with self.assertRaisesRegex(dependencies.DependencyError, 'Incomplete dependency cache'):
                dependencies.ensure_dependencies(self.tool, '/usr/bin/python3')
            install.assert_not_called()
        self.assertEqual((packages / 'user-file').read_text(), 'keep')

    def test_empty_requirements_never_touch_library(self):
        with patch.object(dependencies.subprocess, 'run') as install:
            self.assertIsNone(dependencies.ensure_dependencies(replace(self.tool, requirements_json='[]'), '/usr/bin/python3'))
            install.assert_not_called()
        self.assertFalse(self.root.exists())
