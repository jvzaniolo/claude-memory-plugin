import json
import unittest
from unittest.mock import patch

import test_runtime

runtime = test_runtime.runtime
memory = test_runtime.memory


def feedback(instruction='Títulos de PR em português.', scope='global', key='pr-title'):
    rule = {'key': key, 'scope': scope, 'instruction': instruction, 'evidence': instruction}
    content = memory('pr-language', instruction, 'feedback').decode()
    return content.replace('  type: feedback\n', '  type: feedback\n  rules: ' + json.dumps([rule], ensure_ascii=False) + '\n').encode()


class PreferenceTests(unittest.TestCase):
    tearDown = test_runtime.RuntimeTests.tearDown

    def setUp(self):
        test_runtime.RuntimeTests.setUp(self)
        self.claude = self.state / 'CLAUDE.md'
        self.claude.parent.mkdir(parents=True)
        self.original = b'# Manual\r\n\r\nPreservar exatamente.\r\n'
        self.claude.write_bytes(self.original)

    def test_checkpoint_promotes_explicit_rule_and_preserves_manual_bytes(self):
        def model(work, *args):
            (work / 'alpha-task.md').write_bytes(feedback())
            return {'completed': True, 'used_memories': []}
        with patch.object(runtime, 'model_run', side_effect=model):
            runtime.checkpoint(self.store, {'session_id': 'one', 'lines': 200, 'transcript': []})
        self.assertTrue(self.claude.read_bytes().startswith(self.original))
        self.assertIn('Títulos de PR em português.', self.claude.read_text())
        backups = list((self.state / 'memory-backups').glob('*/instructions/*CLAUDE.md'))
        self.assertEqual(backups[0].read_bytes(), self.original)

    def test_update_changes_only_managed_section_and_retains_other_rules(self):
        data = {'alpha.md': feedback(), 'beta.md': feedback('Commits em inglês.', key='commit-language')}
        first = runtime.update_claude(self.original, runtime.preference_section(data))
        data['alpha.md'] = feedback('Títulos de PR em inglês.')
        second = runtime.update_claude(first, runtime.preference_section(data))
        self.assertTrue(second.startswith(self.original))
        self.assertNotIn('Títulos de PR em português.', second.decode())
        self.assertIn('Títulos de PR em inglês.', second.decode())
        self.assertIn('Commits em inglês.', second.decode())
        self.assertEqual(runtime.update_claude(second, runtime.preference_section(data)), second)
        self.assertIn('só nesta tarefa', second.decode())

    def test_scope_and_supersession(self):
        data = {'alpha.md': feedback(scope='Projeto Hu'), 'beta.md': feedback()}
        data['beta.md'] = data['beta.md'].replace(b'  type: feedback\n', b'  type: feedback\n  superseded_by: [alpha]\n')
        section = runtime.preference_section(data)
        self.assertIn('Projeto Hu', section)
        self.assertEqual(section.count('Títulos de PR em português.'), 1)

    def test_invalid_rule_is_dropped_without_discarding_the_valid_ones(self):
        valid = feedback('Commits em inglês.', key='commit-language')
        for broken in [feedback().replace(b'type: feedback', b'type: project'),
                       feedback().replace(b'"evidence": "T', b'"evidence": "Inventado T'),
                       feedback().replace(b'rules: [', b'rules: nao-e-json [')]:
            with self.subTest(broken=broken):
                section = runtime.preference_section({'alpha.md': broken, 'beta.md': valid})
                self.assertIn('Commits em inglês.', section)
                self.assertNotIn('Títulos de PR em português.', section)

    def test_duplicate_rule_keeps_the_first_and_drops_the_second(self):
        section = runtime.preference_section({'alpha.md': feedback(), 'beta.md': feedback('Outra.')})
        self.assertIn('Títulos de PR em português.', section)
        self.assertNotIn('Outra.', section)

    def test_malformed_markers_fail_without_replacing_manual_content(self):
        for content in [b'<!-- memory:preferences:start -->',
                        b'<!-- memory:preferences:end -->\n<!-- memory:preferences:start -->',
                        b'<!-- memory:preferences:start -->' * 2 + b'<!-- memory:preferences:end -->']:
            with self.subTest(content=content), self.assertRaises(ValueError):
                runtime.update_claude(content, '')

    def test_concurrent_claude_edit_aborts_store_and_checkpoint(self):
        def model(work, *args):
            (work / 'alpha-task.md').write_bytes(feedback())
            self.claude.write_bytes(b'Edicao concorrente\n')
            return {'completed': True, 'used_memories': []}
        with patch.object(runtime, 'model_run', side_effect=model), self.assertRaisesRegex(ValueError, 'instruções mudaram'):
            runtime.checkpoint(self.store, {'session_id': 'one', 'lines': 200, 'transcript': []})
        self.assertEqual(self.claude.read_bytes(), b'Edicao concorrente\n')
        self.assertEqual(runtime.snapshot(self.store), self.before)
        self.assertFalse((self.state / 'memory-checkpoints/one.json').exists())

    def test_no_preferences_leaves_claude_untouched(self):
        self.assertEqual(runtime.update_claude(self.original, runtime.preference_section(self.before)), self.original)

    def test_symlink_is_not_replaced(self):
        target = self.root / 'manual.md'
        target.write_bytes(self.original)
        self.claude.unlink()
        self.claude.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'simbólico'):
            runtime.instruction_snapshot([self.claude])
        self.assertTrue(self.claude.is_symlink())

    def test_existing_oversized_index_does_not_block_unrelated_preference(self):
        self.before['MEMORY.md'] += b'padding ' * 3500
        runtime.stage_files(self.store, self.before)
        (self.store / 'alpha-task.md').write_bytes(feedback())
        changes = runtime.validate_changes(self.store, self.before, 'checkpoint')
        self.assertEqual(set(changes), {'alpha-task.md'})
        (self.store / 'MEMORY.md').write_bytes(self.before['MEMORY.md'] + b'growth')
        with self.assertRaisesRegex(ValueError, 'índice excede'):
            runtime.validate_changes(self.store, self.before, 'checkpoint')
