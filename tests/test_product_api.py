"""Browser test inputs and atomic optimistic editing, with no database migration."""
import asyncio
import json
import tempfile
import unittest
from unittest.mock import patch
from app import main, tool_authoring
from app.database import Database, ToolConflictError


class ProductApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Database(self.temp.name + '/test.db')
        for target in (main, tool_authoring):
            patcher = patch.object(target, 'db', self.db)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.body = main.ToolIn(name='editable', code='print("one")')
        self.saved = asyncio.run(main.api_create_tool(self.body))

    def test_revisions_serialize_in_library(self):
        listed = asyncio.run(main.api_list_tools())['tools'][0]
        self.assertEqual(listed.revision, self.saved['revision'])
        self.assertEqual(len(listed.revision), 64)

    def test_second_tab_cannot_overwrite_new_code(self):
        old = self.saved['revision']
        changed = self.body.model_copy(update={'code': 'print("two")'})
        result = asyncio.run(main.api_update_tool('editable', changed, old))
        self.assertNotEqual(old, result['revision'])
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.api_update_tool('editable', self.body, old))
        self.assertEqual(error.exception.status_code, 412)
        self.assertEqual(self.db.get_tool('editable').code, 'print("two")')

    def test_stale_delete_and_run_do_not_mutate_or_execute(self):
        old = self.saved['revision']
        asyncio.run(main.api_toggle_tool('editable'))
        for operation in (lambda: main.api_delete_tool('editable', old),
                          lambda: main.api_run_tool('editable', None, old)):
            with patch.object(main, 'run_tool') as run:
                with self.assertRaises(main.HTTPException) as error:
                    asyncio.run(operation())
                self.assertEqual(error.exception.status_code, 412)
                run.assert_not_called()
        self.assertIsNotNone(self.db.get_tool('editable'))

    def test_same_name_replacement_is_not_deleted_by_old_tab(self):
        old = self.saved['revision']
        asyncio.run(main.api_delete_tool('editable', old))
        asyncio.run(main.api_create_tool(self.body))
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.api_delete_tool('editable', old))
        self.assertEqual(error.exception.status_code, 412)
        self.assertIsNotNone(self.db.get_tool('editable'))

    def test_database_guard_is_atomic_across_connections(self):
        stale = self.db.get_tool('editable')
        other = Database(self.db.path)
        other.activate('editable', False)
        with self.assertRaises(ToolConflictError):
            self.db.upsert(stale, expected_revision=stale.revision)
        with self.assertRaises(ToolConflictError):
            self.db.delete('editable', expected_revision=stale.revision)
        self.assertFalse(other.get_tool('editable').is_active)

    def test_json_inputs_validate_and_arrive_on_stdin(self):
        body = main.ToolIn(name='greet', code='import json,sys\nargs=json.load(sys.stdin)\nprint(json.dumps({"hello":args["name"]}))',
                           json_schema={'type':'object', 'properties':{'name':{'type':'string'}},
                                        'required':['name'], 'additionalProperties':False})
        saved = asyncio.run(main.api_create_tool(body))
        result = asyncio.run(main.api_run_tool('greet', main.RunIn(arguments={'name':'Ada'}), saved['revision']))
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(json.loads(result['stdout']), {'hello':'Ada'})
        with patch.object(main, 'run_tool') as run:
            with self.assertRaises(main.HTTPException) as error:
                asyncio.run(main.api_run_tool('greet', main.RunIn(arguments={'name':123})))
            self.assertEqual(error.exception.status_code, 422)
            self.assertNotIn('123', error.exception.detail)
            run.assert_not_called()

    def test_no_body_still_defaults_to_empty_object(self):
        result = asyncio.run(main.api_run_tool('editable'))
        self.assertEqual(result['stdout'], 'one')
        self.assertEqual(result['exit_code'], 0)

    def test_schema_validation_prevents_no_body_required_inputs(self):
        body = main.ToolIn(name='requires_input', code='print("should not run")',
                          json_schema={'type':'object','properties':{'x':{'type':'integer'}},'required':['x']})
        asyncio.run(main.api_create_tool(body))
        with patch.object(main, 'run_tool') as run:
            with self.assertRaises(main.HTTPException) as error:
                asyncio.run(main.api_run_tool('requires_input'))
            self.assertEqual(error.exception.status_code, 422)
            run.assert_not_called()

    def test_run_uses_fresh_snapshot_not_other_worker_cache(self):
        self.db.get_tool_list()  # Prime the process-local five-second cache.
        other = Database(self.db.path)
        other.activate('editable', False)
        with patch.object(main, 'run_tool') as run:
            with self.assertRaises(main.HTTPException) as error:
                asyncio.run(main.api_run_tool('editable', None, self.saved['revision']))
            self.assertEqual(error.exception.status_code, 412)
            run.assert_not_called()

    def test_conditional_toggle_rejects_stale_and_recreated_names(self):
        old = self.saved['revision']
        result = asyncio.run(main.api_toggle_tool('editable', old))
        self.assertFalse(result['is_active'])
        self.assertNotEqual(old, result['revision'])
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.api_toggle_tool('editable', old))
        self.assertEqual(error.exception.status_code, 412)
        self.assertFalse(self.db.get_tool('editable').is_active)
        asyncio.run(main.api_delete_tool('editable'))
        asyncio.run(main.api_create_tool(self.body))
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(main.api_toggle_tool('editable', old))
        self.assertEqual(error.exception.status_code, 412)
        self.assertTrue(self.db.get_tool('editable').is_active)

    def test_separate_database_toggles_flip_fresh_state_twice(self):
        other = Database(self.db.path)
        self.assertFalse(self.db.toggle('editable').is_active)
        self.assertTrue(other.toggle('editable').is_active)
