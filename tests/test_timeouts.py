from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app import runner, tool_authoring
from app.database import Database
from app.tool_authoring import ToolIn, save_tool


class TimeoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Database(str(Path(self.temp.name) / 'tools.db'))
        for patcher in (patch.object(tool_authoring, 'db', self.database),
                        patch.object(runner, 'SCRATCH_ROOT', str(Path(self.temp.name) / 'scratch'))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tool(self, **changes):
        fields = {'name':'sample', 'language':'python3', 'code':'print("done")'}
        fields.update(changes)
        return save_tool(ToolIn.model_validate(fields))

    def test_default_and_legacy_migration_are_two_minutes(self):
        self.assertEqual(ToolIn(name='sample', code='print(1)').timeout_seconds, 120)
        self.assertEqual(self.tool().timeout_seconds, 120)
        legacy_path = str(Path(self.temp.name) / 'legacy.db')
        with sqlite3.connect(legacy_path) as conn:
            conn.execute('CREATE TABLE tools (id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL,language TEXT NOT NULL,code TEXT NOT NULL,requirements_json TEXT NOT NULL,json_schema_json TEXT NOT NULL,is_active INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)')
            conn.execute("INSERT INTO tools VALUES ('old','legacy','','python3','print(1)','[]','{}',1,'old','old')")
        migrated = Database(legacy_path)
        self.assertEqual(migrated.get_tool('legacy').timeout_seconds, 120)
        with migrated._connect() as conn:
            column = next(row for row in conn.execute('PRAGMA table_info(tools)') if row['name'] == 'timeout_seconds')
        self.assertEqual(column['notnull'], 1)
        self.assertEqual(int(column['dflt_value']), 120)

    def test_strict_timeout_bounds(self):
        for value in (0, -1, 3601, True, False, 1.5, '45', None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ToolIn(name='sample', code='print(1)', timeout_seconds=value)
        for value in (1, 45, 120, 3600):
            with self.subTest(value=value):
                self.assertEqual(ToolIn(name='sample', code='print(1)', timeout_seconds=value).timeout_seconds, value)

    def test_timeout_persists_changes_revision_and_old_edits_preserve_it(self):
        original = self.tool(timeout_seconds=45)
        saved = Database(self.database.path).get_tool('sample')
        self.assertEqual(saved.timeout_seconds, 45)
        self.assertEqual(saved.revision, original.revision)
        preserved = save_tool(ToolIn(name='sample', code='print(2)'), saved, expected_revision=saved.revision)
        self.assertEqual(preserved.timeout_seconds, 45)
        changed = save_tool(ToolIn(name='sample', code='print(2)', timeout_seconds=90), preserved, expected_revision=preserved.revision)
        self.assertEqual(changed.timeout_seconds, 90)
        self.assertNotEqual(changed.revision, preserved.revision)
        self.assertEqual(Database(self.database.path).get_tool('sample').timeout_seconds, 90)

    def test_configured_45_seconds_is_exactly_forwarded_without_grace(self):
        tool = self.tool(timeout_seconds=45)
        process = Mock(pid=12345, returncode=0, stdin=None, stdout=None, stderr=None)
        process.communicate.return_value = ('done\n', '')
        with patch.object(runner.subprocess, 'Popen', return_value=process) as launch, patch.object(runner, '_kill_process_group') as kill_group:
            result = runner.run_tool(tool)
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertFalse(result.timed_out)
        self.assertEqual(process.communicate.call_args.kwargs['timeout'], 45)
        self.assertTrue(launch.call_args.kwargs['start_new_session'])
        self.assertNotIn('shell', launch.call_args.kwargs)
        kill_group.assert_called_once_with(process)

    def test_invalid_saved_timeout_is_rejected_before_execution(self):
        tool = self.tool()
        for value in (0, 3601, True, '45', None):
            with self.subTest(value=value), patch.object(runner.subprocess, 'Popen') as launch:
                result = runner.run_tool(replace(tool, timeout_seconds=value))
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn('timeout', result.stderr.lower())
                launch.assert_not_called()

    def test_post_kill_output_drain_and_reap_are_bounded(self):
        tool = self.tool(timeout_seconds=45)
        process = Mock(pid=12345, returncode=-9)
        process.communicate.side_effect = [
            subprocess.TimeoutExpired('python', 45, output=b'started'),
            subprocess.TimeoutExpired('python', 1, output=b'started', stderr=b'partial diagnostic'),
        ]
        with patch.object(runner.subprocess, 'Popen', return_value=process), patch.object(runner, '_kill_process_group') as kill_group:
            result = runner.run_tool(tool)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.exit_code, 124)
        self.assertEqual(result.stdout, 'started')
        self.assertIn('partial diagnostic', result.stderr)
        self.assertEqual([call.kwargs['timeout'] for call in process.communicate.call_args_list], [45, 1])
        process.wait.assert_called_once_with(timeout=1)
        kill_group.assert_called_once_with(process)
        for stream in (process.stdin, process.stdout, process.stderr):
            self.assertTrue(stream.close.called)

    def test_real_python_and_node_expire_at_one_second(self):
        for language, code in (('python3', 'import time; print("started", flush=True); time.sleep(10)'),
                               ('node', 'console.log("started"); setTimeout(()=>{},10000);')):
            with self.subTest(language=language):
                tool = self.tool(name='expire_' + language, language=language, code=code, timeout_seconds=1)
                start = time.monotonic()
                with patch.dict(os.environ, {'OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS':'999999'}):
                    result = runner.run_tool(tool)
                elapsed = time.monotonic() - start
                self.assertTrue(result.timed_out, result)
                self.assertEqual(result.exit_code, 124)
                self.assertIn('1s', result.stderr)
                self.assertIn('started', result.stdout)
                self.assertGreaterEqual(elapsed, 0.9)
                self.assertLess(elapsed, 4)

    def test_timeout_kills_ordinary_python_and_node_descendants(self):
        python_code = '''import json, subprocess, sys, time
args = json.load(sys.stdin)
child = "import time; from pathlib import Path; time.sleep(1.5); Path(" + repr(args['marker']) + ").write_text('survived')"
process = subprocess.Popen([sys.executable, '-c', child], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(process.pid, flush=True)
time.sleep(10)
'''
        node_code = '''const fs=require('node:fs'); const cp=require('node:child_process');
const args=JSON.parse(fs.readFileSync(0,'utf8'));
const child=cp.spawn(process.execPath,['-e',"setTimeout(()=>require('node:fs').writeFileSync(process.argv[1],'survived'),1500)",args.marker],{stdio:'ignore'});
console.log(child.pid); setTimeout(()=>{},10000);
'''
        for language, code in (('python3', python_code), ('node', node_code)):
            with self.subTest(language=language):
                marker = Path(self.temp.name) / (language + '.txt')
                tool = self.tool(name='child_' + language, language=language, code=code, timeout_seconds=1)
                result = runner.run_tool(tool, {'marker': str(marker)})
                self.assertTrue(result.timed_out, result.stderr)
                self.assertEqual(result.exit_code, 124)
                child_pid = int(result.stdout)
                time.sleep(0.7)
                self.assertFalse(marker.exists(), 'child wrote a file after the tool deadline')
                stat = Path('/proc') / str(child_pid) / 'stat'
                if stat.exists():
                    self.assertIn(stat.read_text().rsplit(')', 1)[1].split()[0], ('Z', 'X'), 'ordinary child is still running')
        self.assertEqual(list(Path(runner.SCRATCH_ROOT).iterdir()), [])

    def test_exit_code_124_without_deadline_is_not_a_timeout(self):
        result = runner.run_tool(self.tool(code='import sys; sys.exit(124)'))
        self.assertEqual(result.exit_code, 124)
        self.assertFalse(result.timed_out)

    def test_successful_parent_cannot_leave_redirected_ordinary_children_running(self):
        python_code = '''import json, subprocess, sys
args = json.load(sys.stdin)
child = "import time; from pathlib import Path; time.sleep(1.5); Path(" + repr(args['marker']) + ").write_text('survived')"
process = subprocess.Popen([sys.executable, '-c', child], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(process.pid, flush=True)
'''
        node_code = '''const fs=require('node:fs'); const cp=require('node:child_process');
const args=JSON.parse(fs.readFileSync(0,'utf8'));
const child=cp.spawn(process.execPath,['-e',"setTimeout(()=>require('node:fs').writeFileSync(process.argv[1],'survived'),1500)",args.marker],{stdio:'ignore'});
console.log(child.pid); child.unref();
'''
        children = []
        for language, code in (('python3', python_code), ('node', node_code)):
            with self.subTest(language=language):
                marker = Path(self.temp.name) / ('background_' + language + '.txt')
                tool = self.tool(name='background_' + language, language=language, code=code, timeout_seconds=1)
                result = runner.run_tool(tool, {'marker': str(marker)})
                self.assertEqual(result.exit_code, 0, result.stderr)
                self.assertFalse(result.timed_out)
                children.append((marker, int(result.stdout)))
        time.sleep(1.7)
        for marker, child_pid in children:
            self.assertFalse(marker.exists(), 'ordinary background child wrote after its parent returned')
            stat = Path('/proc') / str(child_pid) / 'stat'
            if stat.exists():
                self.assertIn(stat.read_text().rsplit(')', 1)[1].split()[0], ('Z', 'X'), 'ordinary background child is still running')
        self.assertEqual(list(Path(runner.SCRATCH_ROOT).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
