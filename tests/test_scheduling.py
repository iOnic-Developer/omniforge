import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app import runner, tool_authoring
from app.database import Database
from app.runner import RunResult
from app.scheduling import Scheduler, list_folders, next_run_time, validate_folder_path
from app.tool_authoring import ToolIn, save_tool


class SchedulingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'files'
        self.root.mkdir()
        self.database = Database(str(Path(self.temp.name) / 'tools.db'))
        for patcher in (patch.object(tool_authoring, 'db', self.database),
                        patch.dict(os.environ, {'OMNIFORGE_ALLOWED_FOLDERS': str(self.root)}),
                        patch.object(runner, 'SCRATCH_ROOT', str(Path(self.temp.name) / 'scratch'))):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.now = datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc).timestamp()
        self.schedulers = []

    async def asyncTearDown(self):
        for scheduler in self.schedulers:
            await scheduler.stop()

    def create(self, **changes):
        body = {'name': 'sample', 'code': 'print("ok")'}
        body.update(changes)
        return save_tool(ToolIn.model_validate(body))

    def scheduler(self, run=None, **kwargs):
        scheduler = Scheduler(self.database, runner=run or (lambda t, a: RunResult(t.name, t.language, 'ok', '', 0, False, 1)),
                              clock=lambda: self.now, **kwargs)
        self.schedulers.append(scheduler)
        return scheduler

    async def finish(self, scheduler):
        await asyncio.gather(*list(scheduler._running.values()))

    def enable_schedule(self, **changes):
        schedule = {'enabled': True, 'cron': '* * * * *', 'timezone': 'UTC', 'arguments': {}}
        schedule.update(changes)
        return self.create(schedule=schedule)

    def test_old_database_migrates_without_losing_tools(self):
        path = str(Path(self.temp.name) / 'legacy.db')
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE tools(id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL,language TEXT NOT NULL,code TEXT NOT NULL,requirements_json TEXT NOT NULL,json_schema_json TEXT NOT NULL,is_active INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)")
            conn.execute("INSERT INTO tools VALUES ('old','legacy','','python3','print(1)','[]','{}',1,'2020','2020')")
        migrated = Database(path).get_tool('legacy')
        self.assertEqual(migrated.code, 'print(1)')
        self.assertIsNone(migrated.schedule)
        self.assertIsNone(migrated.folder_access)

    def test_settings_persist_and_change_content_revision(self):
        tool = self.create()
        body = ToolIn(name=tool.name, code=tool.code, schedule={'cron': '0 2 * * *'},
                      folder_access={'enabled': True, 'path': str(self.root / 'docs')})
        updated = save_tool(body, tool, expected_revision=tool.revision)
        saved = Database(self.database.path).get_tool('sample')
        self.assertNotEqual(tool.revision, updated.revision)
        self.assertEqual(saved.revision, updated.revision)
        self.assertEqual(saved.schedule['cron'], '0 2 * * *')
        self.assertEqual(saved.folder_access['path'], str(self.root / 'docs'))
        self.assertFalse((self.root / 'docs').exists(), 'saving must not create output folders')

    def test_old_clients_preserve_settings_and_explicit_null_removes(self):
        tool = self.create(schedule={'cron': '0 2 * * *'}, folder_access={'path': str(self.root)})
        preserved = save_tool(ToolIn(name=tool.name, code='print(2)'), tool)
        self.assertEqual(preserved.schedule, tool.schedule)
        self.assertEqual(preserved.folder_access, tool.folder_access)
        cleared = save_tool(ToolIn(name=tool.name, code='print(3)', schedule=None, folder_access=None), preserved)
        self.assertIsNone(cleared.schedule)
        self.assertIsNone(cleared.folder_access)

    def test_cron_and_timezone_validation(self):
        for cron in ('* * * * * *', '@daily', '99 * * * *', '0 0 30 2 *', '0 0 * * ?'):
            with self.subTest(cron=cron), self.assertRaises(ValidationError):
                ToolIn(name='test', code='print(1)', schedule={'cron': cron})
        with self.assertRaises(ValidationError):
            ToolIn(name='test', code='print(1)', schedule={'timezone': 'not/a-zone'})
        with self.assertRaises(ValidationError):
            ToolIn(name='test', code='print(1)', schedule={'enabled': 'yes'})
        start = datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp()
        next_at = next_run_time('0 2 * * *', 'Europe/London', start)
        self.assertEqual(datetime.fromtimestamp(next_at, timezone.utc).hour, 1)

    def test_london_dst_transition_retains_local_nightly_time(self):
        before = datetime(2026, 10, 24, 3, 0, tzinfo=timezone.utc).timestamp()
        autumn = next_run_time('0 2 * * *', 'Europe/London', before)
        self.assertEqual(datetime.fromtimestamp(autumn, timezone.utc).hour, 2)
        before = datetime(2026, 3, 28, 3, 0, tzinfo=timezone.utc).timestamp()
        spring = next_run_time('0 2 * * *', 'Europe/London', before)
        self.assertEqual(datetime.fromtimestamp(spring, timezone.utc).hour, 1)

    def test_scheduled_arguments_are_validated(self):
        schema = {'type': 'object', 'properties': {'url': {'type': 'string'}}, 'required': ['url']}
        with self.assertRaises(ValidationError):
            ToolIn(name='test', code='print(1)', json_schema=schema, schedule={'enabled': True})
        tool = self.create(json_schema=schema, schedule={'enabled': True, 'arguments': {'url': 'https://example.com/doc'}})
        self.assertEqual(tool.schedule['arguments']['url'], 'https://example.com/doc')

    def test_folders_reject_escape_and_list_directories_only(self):
        (self.root / 'docs').mkdir()
        (self.root / 'document.txt').write_text('data')
        with self.assertRaises(ValueError):
            validate_folder_path(str(self.root / '..' / 'outside'))
        with self.assertRaises(ValueError):
            validate_folder_path('relative')
        with self.assertRaises(ValueError):
            validate_folder_path(self.temp.name)
        outside = Path(self.temp.name) / 'private'
        outside.mkdir()
        (self.root / 'escape').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            validate_folder_path(str(self.root / 'escape' / 'subdir'))
        listed = list_folders(str(self.root))
        self.assertEqual([item['name'] for item in listed['folders']], ['docs'])
        self.assertEqual(list_folders()['roots'], [str(self.root)])
        with self.assertRaises(ValidationError):
            ToolIn(name='test', code='print(1)', folder_access={'enabled': True})

    async def test_due_run_persists_history_and_next_time_across_restart(self):
        tool = self.enable_schedule()
        scheduler = self.scheduler()
        self.assertEqual(await scheduler.tick(), 0)
        next_at = scheduler.get_status(tool.id)['next_run_at']
        self.now += 61
        self.assertEqual(await scheduler.tick(), 1)
        await self.finish(scheduler)
        state = scheduler.get_status(tool.id)
        self.assertEqual(state['last_status'], 'success')
        self.assertEqual(state['last_exit_code'], 0)
        self.assertNotEqual(state['next_run_at'], next_at)
        self.assertEqual(len(state['history']), 1)
        restarted = self.scheduler()
        self.assertEqual(restarted.get_status(tool.id)['next_run_at'], state['next_run_at'])
        self.assertEqual(await restarted.tick(), 0)

    async def test_paused_and_inactive_tools_do_not_run_then_resume_next_cron(self):
        tool = self.enable_schedule()
        scheduler = self.scheduler()
        await scheduler.tick()
        paused = replace(tool, schedule={**tool.schedule, 'enabled': False})
        self.database.upsert(paused)
        self.now += 120
        self.assertEqual(await scheduler.tick(), 0)
        self.assertIsNone(scheduler.get_status(tool.id)['next_run_at'])
        self.database.upsert(tool)
        self.assertEqual(await scheduler.tick(), 0)
        self.now += 61
        self.database.activate(tool.name, False)
        self.assertEqual(await scheduler.tick(), 0)
        self.assertIsNone(scheduler.get_status(tool.id)['next_run_at'])
        self.database.activate(tool.name, True)
        self.assertEqual(await scheduler.tick(), 0)
        self.now += 61
        self.assertEqual(await scheduler.tick(), 1)
        await self.finish(scheduler)

    async def test_missed_runs_coalesce_and_multiple_workers_claim_once(self):
        tool = self.enable_schedule()
        first, second = self.scheduler(), self.scheduler()
        await first.tick()
        self.now += 86400
        counts = await asyncio.gather(first.tick(), second.tick())
        self.assertEqual(sum(counts), 1)
        await self.finish(first)
        await self.finish(second)
        self.assertEqual(len(first.get_status(tool.id)['history']), 1)
        self.assertEqual(await first.tick(), 0)

    async def test_edit_after_claim_skips_stale_snapshot(self):
        calls = []
        def run(tool, args):
            calls.append(tool.code)
            return RunResult(tool.name, tool.language, '', '', 0, False, 1)
        tool = self.enable_schedule()
        scheduler = self.scheduler(run)
        await scheduler.tick()
        self.now += 61
        self.assertEqual(await scheduler.tick(), 1)
        self.database.upsert(replace(tool, code='print("changed after claim")'))
        await self.finish(scheduler)
        self.assertEqual(calls, [])
        self.assertEqual(scheduler.get_status(tool.id)['last_status'], 'skipped')

    async def test_runtime_schema_is_revalidated(self):
        calls = []
        def run(tool, args):
            calls.append(tool.id)
            return RunResult(tool.name, tool.language, '', '', 0, False, 1)
        tool = self.enable_schedule()
        self.database.upsert(replace(tool, json_schema_json=json.dumps({'type':'object','required':['url']})))
        scheduler = self.scheduler(run)
        await scheduler.tick()
        self.now += 61
        await scheduler.tick()
        await self.finish(scheduler)
        self.assertEqual(calls, [])
        self.assertEqual(scheduler.get_status(tool.id)['last_status'], 'failed')

    async def test_running_tool_does_not_overlap_or_exceed_concurrency(self):
        began, release = threading.Event(), threading.Event()
        calls = []
        def run(tool, args):
            calls.append(tool.id)
            began.set()
            release.wait(5)
            return RunResult(tool.name, tool.language, '', '', 0, False, 1)
        tool = self.enable_schedule()
        self.create(name='second', schedule=tool.schedule)
        scheduler = self.scheduler(run, max_concurrency=1)
        await scheduler.tick()
        self.now += 61
        self.assertEqual(await scheduler.tick(), 1)
        await asyncio.to_thread(began.wait, 2)
        self.assertTrue(scheduler.get_status(tool.id)['running'])
        self.now += 61
        self.assertEqual(await scheduler.tick(), 0)
        self.assertEqual(len(calls), 1)
        release.set()
        await self.finish(scheduler)

    async def test_expired_claim_is_recorded_as_interrupted_without_replaying(self):
        tool = self.enable_schedule()
        scheduler = self.scheduler()
        await scheduler.tick()
        with self.database._connect() as conn:
            conn.execute("UPDATE tool_schedule_state SET claim_token='old',lease_until=?,last_status='running' WHERE tool_id=?", (self.now - 1, tool.id))
            conn.execute("INSERT INTO tool_schedule_runs(id,tool_id,started_at,status) VALUES ('old',?,?,'running')", (tool.id,self.now-100))
        self.assertEqual(await scheduler.tick(), 0)
        state = scheduler.get_status(tool.id)
        self.assertEqual(state['last_status'], 'interrupted')
        self.assertFalse(state['running'])
        self.assertEqual(state['history'][0]['status'], 'interrupted')

    async def test_failure_records_status_without_storing_script_output(self):
        def run(tool,args):
            return RunResult(tool.name,tool.language,'private output','private error',3,False,5)
        tool = self.enable_schedule()
        scheduler = self.scheduler(run)
        await scheduler.tick()
        self.now += 61
        await scheduler.tick()
        await self.finish(scheduler)
        state = scheduler.get_status(tool.id)
        self.assertEqual(state['last_status'], 'failed')
        self.assertEqual(state['last_exit_code'], 3)
        self.assertNotIn('private', json.dumps(state))

    async def test_lease_is_renewed_while_script_runs(self):
        began, release = threading.Event(), threading.Event()
        def run(tool, args):
            began.set()
            release.wait(5)
            return RunResult(tool.name, tool.language, '', '', 0, False, 1)
        tool = self.enable_schedule()
        first = self.scheduler(run, lease_seconds=3)
        second = self.scheduler(lease_seconds=3)
        await first.tick()
        self.now += 61
        await first.tick()
        await asyncio.to_thread(began.wait, 2)
        self.now += 2
        await asyncio.sleep(1.05)
        self.now += 2
        self.assertEqual(await second.tick(), 0)
        self.assertTrue(second.get_status(tool.id)['running'])
        release.set()
        await self.finish(first)

    async def test_cancelled_task_keeps_claim_until_actual_script_finishes(self):
        began, release = threading.Event(), threading.Event()
        calls = []
        def run(tool, args):
            calls.append(tool.id)
            began.set()
            release.wait(5)
            return RunResult(tool.name, tool.language, '', '', 0, False, 1)
        tool = self.enable_schedule()
        first, second = self.scheduler(run, lease_seconds=3), self.scheduler(run, lease_seconds=3)
        await first.tick()
        self.now += 61
        await first.tick()
        await asyncio.to_thread(began.wait, 2)
        execution = first._running[tool.id]
        execution.cancel()
        heartbeats = [task for task in asyncio.all_tasks()
                      if task.get_coro().__qualname__ == 'Scheduler._heartbeat']
        self.assertEqual(len(heartbeats), 1)
        heartbeats[0].cancel()
        await asyncio.sleep(0.01)
        self.assertFalse(execution.done(), 'cancellation must wait for the script thread')
        self.assertTrue(first.get_status(tool.id)['running'])
        self.now += 58
        await asyncio.sleep(1.05)
        self.now += 2
        self.assertEqual(await second.tick(), 0)
        self.assertTrue(second.get_status(tool.id)['running'])
        self.assertEqual(len(calls), 1)
        release.set()
        await asyncio.gather(execution, return_exceptions=True)
        self.assertTrue(execution.cancelled())
        state = first.get_status(tool.id)
        self.assertEqual(state['last_status'], 'success')
        self.assertFalse(state['running'])

    async def test_scheduled_download_writes_real_response_to_selected_folder(self):
        document_root = Path(self.temp.name) / 'server'
        document_root.mkdir()
        (document_root / 'latest.txt').write_text('latest document from HTTP')
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(document_root)))
        serving = threading.Thread(target=server.serve_forever, daemon=True)
        serving.start()
        try:
            tool = self.create(schedule={'enabled':True,'cron':'* * * * *','timezone':'UTC',
                              'arguments':{'url': f'http://127.0.0.1:{server.server_port}/latest.txt'}},
                              json_schema={'type':'object','properties':{'url':{'type':'string'}},'required':['url']})
            tool = replace(tool,
                code='import json, os, sys\nfrom pathlib import Path\nfrom urllib.request import urlopen\nargs=json.load(sys.stdin)\nwith urlopen(args["url"],timeout=3) as response:\n    Path(os.environ["OMNIFORGE_OUTPUT_DIR"],"latest.txt").write_bytes(response.read())\nprint("saved")',
                json_schema_json=json.dumps({'type':'object','properties':{'url':{'type':'string'}},'required':['url']}),
                folder_access={'enabled': True, 'path': str(self.root / 'downloads')})
            self.database.upsert(tool)
            scheduler = self.scheduler(runner.run_tool)
            await scheduler.tick()
            self.now += 61
            await scheduler.tick()
            await self.finish(scheduler)
            self.assertEqual(scheduler.get_status(tool.id)['last_status'], 'success')
            self.assertEqual((self.root / 'downloads' / 'latest.txt').read_text(), 'latest document from HTTP')
        finally:
            await asyncio.to_thread(server.shutdown)
            server.server_close()
            serving.join(timeout=2)

    async def test_deleted_tool_removes_schedule_and_history(self):
        tool = self.enable_schedule()
        scheduler = self.scheduler()
        await scheduler.tick()
        self.now += 61
        await scheduler.tick()
        await self.finish(scheduler)
        self.database.delete(tool.name)
        self.assertEqual(scheduler.get_status(tool.id)['history'], [])
        self.assertEqual(await scheduler.tick(), 0)

    async def test_background_lifecycle_stops_cleanly(self):
        self.enable_schedule()
        scheduler = self.scheduler(poll_interval=0.1)
        await scheduler.start()
        await asyncio.sleep(0.01)
        self.assertIsNotNone(scheduler._loop_task)
        await scheduler.stop()
        self.assertIsNone(scheduler._loop_task)

    def test_python_and_node_write_to_configured_folder(self):
        for language, code in (
            ('python3', 'import os\nfrom pathlib import Path\nPath(os.environ["OMNIFORGE_OUTPUT_DIR"],"python.txt").write_text("downloaded")\nprint(Path.cwd())'),
            ('node', 'const fs=require("node:fs"); const path=require("node:path"); fs.writeFileSync(path.join(process.env.OMNIFORGE_OUTPUT_DIR,"node.txt"),"downloaded"); console.log(process.cwd());')):
            with self.subTest(language=language):
                tool = self.create(name='write_' + language, language=language, code=code,
                                   folder_access={'enabled': True, 'path': str(self.root / 'downloads')})
                result = runner.run_tool(tool, {})
                self.assertEqual(result.exit_code, 0, result.stderr)
                self.assertEqual(result.stdout, str(self.root / 'downloads'))
        self.assertEqual((self.root/'downloads'/'python.txt').read_text(), 'downloaded')
        self.assertEqual((self.root/'downloads'/'node.txt').read_text(), 'downloaded')
        self.assertEqual(list(Path(runner.SCRATCH_ROOT).iterdir()), [])

    def test_output_variable_not_inherited_without_folder_feature(self):
        tool = self.create(code='import os; print(os.environ.get("OMNIFORGE_OUTPUT_DIR", "absent"))')
        with patch.dict(os.environ, {'OMNIFORGE_OUTPUT_DIR':'another-tool-folder'}):
            self.assertEqual(runner.run_tool(tool).stdout, 'absent')

    def test_folder_revalidated_if_symlink_changes_after_save(self):
        destination = self.root / 'downloads'
        tool = self.create(folder_access={'enabled':True,'path':str(destination)})
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        destination.symlink_to(outside, target_is_directory=True)
        result = runner.run_tool(tool)
        self.assertEqual(result.exit_code, 1)
        self.assertIn('allowed folder', result.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_concurrent_runs_have_distinct_script_paths(self):
        tool = self.create(code='import time; time.sleep(0.05); print("first")')
        changed = replace(tool, code='import time; time.sleep(0.05); print("second")')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(runner.run_tool, (tool, changed)))
        self.assertEqual([result.stdout for result in results], ['first', 'second'])


if __name__ == '__main__':
    unittest.main()
