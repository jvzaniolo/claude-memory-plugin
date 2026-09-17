import contextlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime', ROOT / 'scripts/runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def memory(name, body='', kind='project'):
    return f'---\nname: {name}\ndescription: fixture\nmetadata:\n  type: {kind}\n  modified: 2020-01-01\n---\n{body}\n'.encode()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        self.store = self.root / 'store'
        self.store.mkdir()
        self.state = self.root / 'state'
        self.env = patch.dict(os.environ, {'MEM_STORE': str(self.store), 'MEM_STATE_DIR': str(self.state)})
        self.env.start()
        self.before = {'MEMORY.md': b'# Index\n- [Dossier](topic-dossier.md)\n',
                       'topic-dossier.md': memory('topic-dossier', '[[alpha-task]]\n[[beta-task]]'),
                       'alpha-task.md': memory('alpha-task'), 'beta-task.md': memory('beta-task')}
        runtime.stage_files(self.store, self.before)
        self.candidates = [{'arquivo': 'alpha-task.md', 'dossie': 'topic-dossier.md'},
                           {'arquivo': 'beta-task.md', 'dossie': 'topic-dossier.md'}]

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def select(self, *args, **kwargs):
        return subprocess.CompletedProcess(args, 0, json.dumps({'candidatos': self.candidates}), '')

    def test_model_command_has_isolation_and_no_session_resume(self):
        command = runtime.claude_command(self.store, 'consolidate', ['topic-dossier.md'], self.root / 'prompt')
        for flag in ['--safe-mode', '--restricted', '--strict-mcp-config', '--no-session-persistence']:
            self.assertIn(flag, command)
        self.assertNotIn('--resume', command)
        self.assertEqual(command[command.index('--tools') + 1], 'Read,Write,Edit,Glob,Grep')
        self.assertEqual(command[command.index('--permission-mode') + 1], 'dontAsk')
        settings = json.loads(command[command.index('--settings') + 1])
        self.assertTrue(settings['disableAllHooks'])
        self.assertEqual(settings['permissions']['allow'][-1], f'Edit(/{self.store}/topic-dossier.md)')

    def test_partial_report_marks_only_named_file_and_retries(self):
        report = {'results': [{'file': 'alpha-task.md', 'status': 'already_summarized'}]}
        with patch.object(runtime.subprocess, 'run', side_effect=self.select), patch.object(runtime, 'model_run', return_value=report):
            with self.assertRaisesRegex(ValueError, 'parcial'):
                runtime.consolidate(self.store, True)
        state = json.loads((self.state / 'memory-consolidated.json').read_text())
        self.assertEqual(set(state), {'alpha-task.md'})
        self.assertFalse((self.state / '.memory-consolidate-last-run').exists())

    def test_skipped_file_remains_pending(self):
        report = {'results': [{'file': 'alpha-task.md', 'status': 'skipped'},
                              {'file': 'beta-task.md', 'status': 'already_summarized'}]}
        with patch.object(runtime.subprocess, 'run', side_effect=self.select), patch.object(runtime, 'model_run', return_value=report):
            with self.assertRaisesRegex(ValueError, 'parcial'):
                runtime.consolidate(self.store)
        self.assertEqual(set(json.loads((self.state / 'memory-consolidated.json').read_text())), {'beta-task.md'})

    def test_duplicate_and_unknown_results_are_rejected(self):
        row = {'file': 'alpha-task.md', 'status': 'consolidated'}
        for rows in [[row, row], [{'file': 'alien.md', 'status': 'consolidated'}], [{'file': 'alpha-task.md', 'status': 'done'}]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                runtime.validate_report({'results': rows}, 'consolidate', self.candidates)

    def test_text_report_cannot_confirm_anything(self):
        with self.assertRaises(ValueError):
            runtime.validate_report({'result': 'consolidada|alpha-task.md'}, 'consolidate', self.candidates)

    def test_failure_and_bad_envelope_do_not_advance_checkpoint(self):
        request = {'session_id': 'fixture', 'lines': 200, 'transcript': []}
        with patch.object(runtime, 'model_run', side_effect=ValueError('network error')):
            with self.assertRaises(ValueError):
                runtime.checkpoint(self.store, request)
        self.assertFalse((self.state / 'memory-checkpoints/fixture.json').exists())
        self.assertEqual(runtime.snapshot(self.store), self.before)

    def test_consolidation_cannot_edit_topic_or_index(self):
        for name in ['alpha-task.md', 'MEMORY.md']:
            with self.subTest(name=name):
                (self.store / name).write_bytes(self.before[name] + b'changed\n')
                with self.assertRaisesRegex(ValueError, 'não autorizado'):
                    runtime.validate_changes(self.store, self.before, 'consolidate', self.candidates,
                                             {'alpha-task.md': 'consolidated'})
                (self.store / name).write_bytes(self.before[name])

    def test_deletion_and_symlink_are_rejected(self):
        (self.store / 'alpha-task.md').unlink()
        with self.assertRaisesRegex(ValueError, 'apagar'):
            runtime.validate_changes(self.store, self.before, 'checkpoint')
        (self.store / 'alpha-task.md').symlink_to(self.store / 'beta-task.md')
        with self.assertRaisesRegex(ValueError, 'simbólico'):
            runtime.validate_changes(self.store, self.before, 'checkpoint')

    def test_store_change_during_model_call_aborts_apply(self):
        (self.store / 'alpha-task.md').write_bytes(b'concurrent edit')
        with self.assertRaisesRegex(ValueError, 'mudou'):
            runtime.apply_changes(self.store, self.before, {'topic-dossier.md': b'worker edit'})
        self.assertEqual((self.store / 'topic-dossier.md').read_bytes(), self.before['topic-dossier.md'])

    def test_usage_is_idempotent_per_session(self):
        changes = {}
        runtime.record_usage(self.before, changes, ['alpha-task.md'], 'one-session')
        before = self.before | changes
        runtime.record_usage(before, changes, ['alpha-task.md'], 'one-session')
        self.assertEqual(json.loads(changes['.memory-usage.json'])['alpha-task.md']['uses'], 1)
        runtime.record_usage(before | changes, changes, ['alpha-task.md'], 'another-session')
        self.assertEqual(json.loads(changes['.memory-usage.json'])['alpha-task.md']['uses'], 2)

    def test_lock_serializes_modes_and_releases_after_process_death(self):
        code = ('import importlib.util,sys,time;'
                f's=importlib.util.spec_from_file_location("r",{str(ROOT / "scripts/runtime.py")!r});'
                'r=importlib.util.module_from_spec(s);s.loader.exec_module(r);'
                'c=r.store_lock(r.memory_store());c.__enter__();print("locked",flush=True);time.sleep(30)')
        child = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'locked')
            with self.assertRaises(BlockingIOError):
                with runtime.store_lock(self.store):
                    pass
        finally:
            child.kill()
            child.wait()
            child.stdout.close()
        with runtime.store_lock(self.store):
            pass

    def test_checkpoint_applies_valid_change_and_keeps_backup(self):
        def model(work, *args):
            (work / 'alpha-task.md').write_bytes(self.before['alpha-task.md'] + b'new fact\n')
            return {'completed': True, 'used_memories': ['alpha-task.md']}
        with patch.object(runtime, 'model_run', side_effect=model):
            runtime.checkpoint(self.store, {'session_id': 'fixture', 'lines': 200, 'transcript': []})
        self.assertIn(b'new fact', (self.store / 'alpha-task.md').read_bytes())
        self.assertEqual(json.loads((self.state / 'memory-checkpoints/fixture.json').read_text())['lines'], 200)
        backups = list((self.state / 'memory-backups').glob('*/alpha-task.md'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.before['alpha-task.md'])

    def test_completed_batch_advances_daily_marker(self):
        report = {'results': [{'file': c['arquivo'], 'status': 'already_summarized'} for c in self.candidates]}
        with patch.object(runtime.subprocess, 'run', side_effect=self.select), patch.object(runtime, 'model_run', return_value=report):
            runtime.consolidate(self.store, True)
        self.assertTrue((self.state / '.memory-consolidate-last-run').exists())
        self.assertEqual(len(json.loads((self.state / 'memory-consolidated.json').read_text())), 2)

    def test_empty_candidates_do_not_invoke_model(self):
        with patch.object(runtime.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{"candidatos":[]}', '')), patch.object(runtime, 'model_run') as model:
            runtime.consolidate(self.store, True)
            model.assert_not_called()
        self.assertTrue((self.state / '.memory-consolidate-last-run').exists())


if __name__ == '__main__':
    unittest.main()
