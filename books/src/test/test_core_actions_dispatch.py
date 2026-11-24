#!/usr/bin/env python3
"""Core actions: dispatch, unknown actions, settings and the LLM bridge."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:core', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

class ActionDispatchTest(unittest.TestCase):
    def setUp(self):
        self.actions = _fixture.load_module(BOOK_ROOT, 'actions')

    def test_every_advertised_action_has_a_handler(self):
        handlers = set(self.actions.DISPATCH)
        handlers.add('llm-ask')
        self.assertEqual(handlers, set(self.actions.ACTIONS))

    def test_unknown_action_returns_two_with_the_known_list(self):
        code, text = self.actions.run('nope')
        self.assertEqual(code, 2)
        self.assertIn('unknown action', text)

    def test_dispatch_invokes_the_handler_and_logs(self):
        handler = mock.Mock(return_value=(0, 'ok'))
        with mock.patch.dict(self.actions.DISPATCH, {'status': handler}):
            code, text = self.actions.run('status')
        self.assertEqual((code, text), (0, 'ok'))
        handler.assert_called_once()

    def test_llm_ask_routes_through_the_llm_layer(self):
        with mock.patch.object(self.actions._llm, 'complete', return_value='回答') as complete:
            code, text = self.actions.run('llm-ask', prompt='问', scenario='summary')
        self.assertEqual(code, 0)
        self.assertIn('回答', text)
        self.assertEqual(complete.call_args.args[0], '问')

    def test_llm_ask_reports_a_provider_error_as_code_two(self):
        with mock.patch.object(self.actions._llm, 'complete',
                               side_effect=self.actions._llm.LLMError('down')):
            code, text = self.actions.run('llm-ask', prompt='问')
        self.assertEqual(code, 2)
        self.assertIn('down', text)

    def test_the_child_environment_carries_the_selection(self):
        with mock.patch.dict(self.actions._SELECTION, {'book': '/b', 'edition': 'abridged'}):
            env = self.actions.child_env()
        self.assertEqual(env['BOOK_ROOT'], '/b')
        self.assertEqual(env['BOOK_EDITION'], 'abridged')

    def test_an_empty_selection_leaves_the_environment_alone(self):
        with mock.patch.dict(self.actions._SELECTION, {'book': '', 'edition': ''}):
            env = self.actions.child_env()
        self.assertNotIn('BOOK_ROOT', env)
        self.assertNotIn('BOOK_EDITION', env)

    def test_a_run_collects_both_streams(self):
        done = mock.Mock(returncode=1, stdout='out\n', stderr='err\n')
        with mock.patch.object(self.actions.subprocess, 'run', return_value=done):
            code, text = self.actions._run('merge.py')
        self.assertEqual(code, 1)
        self.assertEqual(text, 'out\nerr\n')

    def test_make_is_called_through_the_same_helper(self):
        done = mock.Mock(returncode=0, stdout='ok\n', stderr='')
        with mock.patch.object(self.actions.subprocess, 'run', return_value=done) as run:
            code, text = self.actions._make('check', '--only', 'lint')
        self.assertEqual((code, text), (0, 'ok\n'))
        self.assertIn('make.py', run.call_args[0][0][1])

    def test_the_llm_usage_lines_name_a_failed_ledger(self):
        class Boom(Exception):
            pass

        with mock.patch.object(self.actions._llm, 'budget_line', side_effect=Boom('磁盘满')):
            self.actions._llm.LLMError = Boom
            line = self.actions._llm_lines()
        self.assertIn('用量记账不可用', line)

    def test_status_survives_an_llm_layer_that_cannot_answer(self):
        class Boom(Exception):
            pass

        with mock.patch.object(self.actions._llm, 'status', side_effect=Boom('无配置')):
            self.actions._llm.LLMError = Boom
            code, text = self.actions.status()
        self.assertEqual(code, 0, text[-200:])
        self.assertIn('llm       :', text)

    def test_the_volume_line_says_when_there_is_nothing_to_compare(self):
        code, line = self.actions._volume_line('not json')
        self.assertEqual(code, 0)
        self.assertIn('无基线可比', line)

    def test_the_volume_line_flags_a_shrunk_manuscript(self):
        code, line = self.actions._volume_line('{"count": 2}')
        self.assertEqual(code, 1)
        self.assertIn('2 项低于基线', line)
        self.assertIn('--update-baseline', line)

    def test_the_estimate_names_the_price_and_the_day_so_far(self):
        guess = {'model': 'm', 'prompt_tokens': 10, 'max_tokens': 20,
                 'cost_low': 0.001, 'cost_high': 0.002, 'currency': 'USD'}
        with mock.patch.object(self.actions._llm, 'estimate', return_value=guess), \
                mock.patch.object(self.actions._llm, 'today_cost', return_value=0.5):
            line = self.actions.estimate_line('写一段小结')
        self.assertIn('≈ 0.0010-0.0020 USD', line)
        self.assertIn('今日已用', line)

    def test_an_unpriced_model_says_so_instead_of_inventing_a_number(self):
        guess = {'model': '', 'prompt_tokens': 1, 'max_tokens': 2,
                 'cost_low': None, 'cost_high': None, 'currency': 'USD'}
        with mock.patch.object(self.actions._llm, 'estimate', return_value=guess), \
                mock.patch.object(self.actions._llm, 'today_cost', return_value=0.0):
            line = self.actions.estimate_line('写一段小结')
        self.assertIn('未定价', line)
        self.assertNotIn('今日已用', line)

    def test_analyze_runs_three_stage_scripts_then_the_volume_check(self):
        calls = []

        def fake_run(script, *args):
            calls.append(script)
            return 0, ''

        with mock.patch.object(self.actions, '_run', side_effect=fake_run):
            code, text = self.actions.analyze()
        self.assertEqual(code, 0)
        self.assertEqual([os.path.basename(c) for c in calls],
                         ['digest.py', 'outline.py', 'chapters.py', 'content_volume.py'])
        self.assertIn('内容体积', text)

    def test_analyze_with_llm_passes_the_flag_only_to_chapters(self):
        calls = []

        def fake_run(script, *args):
            calls.append((os.path.basename(script), args))
            return 0, ''

        with mock.patch.object(self.actions, '_run', side_effect=fake_run):
            self.actions.analyze(use_llm=True)
        self.assertEqual(calls[2], ('chapters.py', ('--llm',)))
        self.assertEqual(calls[0], ('digest.py', ()))

    def test_analyze_passes_force_only_when_asked(self):
        calls = []

        def fake_run(script, *args):
            calls.append((os.path.basename(script), args))
            return 0, ''

        with mock.patch.object(self.actions, '_run', side_effect=fake_run):
            self.actions.analyze(force=True)
        self.assertEqual(calls[2], ('chapters.py', ('--force',)))

    def test_analyze_passes_refresh_only_when_asked(self):
        calls = []

        def fake_run(script, *args):
            calls.append((os.path.basename(script), args))
            return 0, ''

        with mock.patch.object(self.actions, '_run', side_effect=fake_run):
            self.actions.analyze(refresh=True)
        self.assertEqual(calls[2], ('chapters.py', ('--refresh-facts',)))

    def test_dispatched_analyze_forwards_the_switches(self):
        seen = {}

        def fake_run(script, *args):
            if script.endswith('chapters.py'):
                seen['args'] = args
            return 0, ''

        with mock.patch.object(self.actions, '_run', side_effect=fake_run):
            code, _text = self.actions.run('analyze', refresh=True)
        self.assertEqual(code, 0)
        self.assertEqual(seen['args'], ('--refresh-facts',))

    def test_the_refresh_action_is_advertised_and_dispatched(self):
        self.assertIn('analyze-refresh', self.actions.ACTIONS)
        self.assertIn('analyze-refresh', self.actions.DISPATCH)

    def test_a_zero_call_llm_run_explains_why(self):
        def fake_run(script, *args):
            return 0, ''

        with mock.patch.object(self.actions, '_run', side_effect=fake_run), \
                mock.patch.object(self.actions._llm, 'take_totals', return_value={}), \
                mock.patch.object(self.actions._llm, 'since',
                                  return_value={'calls': 0}):
            _code, text = self.actions.analyze(use_llm=True)
        self.assertIn('没有触发导读/小结润色', text)

    def test_analyze_reports_a_shrunk_manuscript_as_a_failure(self):
        payload = '{"count": 2, "problems": ["ch1: bytes below floor"]}'

        def fake_run(script, *args):
            if script.endswith('content_volume.py'):
                return 0, payload
            return 0, ''

        with mock.patch.object(self.actions, '_run', side_effect=fake_run):
            code, text = self.actions.analyze()
        self.assertEqual(code, 1)
        self.assertIn('2 项低于基线', text)
        self.assertIn('--update-baseline', text)

    def test_analyze_without_a_baseline_stays_advisory(self):
        def fake_run(script, *args):
            return (0, 'no baseline yet' if script.endswith('content_volume.py') else '')

        with mock.patch.object(self.actions, '_run', side_effect=fake_run):
            code, text = self.actions.analyze()
        self.assertEqual(code, 0)
        self.assertIn('无基线', text)

    def test_a_failing_stage_stops_the_pipeline(self):
        def fake_run(script, *args):
            return (1 if script.endswith('outline.py') else 0), ''

        with mock.patch.object(self.actions, '_run', side_effect=fake_run):
            code, _text = self.actions.analyze()
        self.assertEqual(code, 1)

    def test_settings_table_lists_the_writable_keys(self):
        rows = [{'key': 'book.title', 'value': 'X', 'description': '书名'}]
        with mock.patch.dict('sys.modules', {}), \
                mock.patch('core.settings.list_settings', return_value=rows):
            code, text = self.actions.settings_table()
        self.assertEqual(code, 0)
        self.assertIn('book.title', text)


class DeliverAllTest(unittest.TestCase):
    """The full-delivery action: every artifact, in dependency order, stop on failure."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.actions = _fixture.load_module(self.root, 'actions')

    def test_it_builds_then_delivers_then_prints(self):
        calls = []

        def fake_make(mode, on_line=None):
            calls.append(('make', mode))
            return 0, f'{mode} ok\n'

        def fake_run(script, *args, on_line=None):
            calls.append(('run', script))
            return 0, f'{script} ok\n'

        with mock.patch.object(self.actions, '_make', side_effect=fake_make), \
                mock.patch.object(self.actions, '_run', side_effect=fake_run):
            code, text = self.actions.deliver_all()
        self.assertEqual(code, 0)
        self.assertEqual([call[1] for call in calls],
                         ['build', 'deliver', 'render/print_pdf.py'])
        self.assertIn('print_pdf.py ok', text)

    def test_a_failed_step_stops_the_run(self):
        calls = []

        def fake_make(mode, on_line=None):
            calls.append(mode)
            return (0, 'build ok\n') if mode == 'build' else (1, 'deliver failed\n')

        with mock.patch.object(self.actions, '_make', side_effect=fake_make), \
                mock.patch.object(self.actions, '_run') as run:
            code, text = self.actions.deliver_all()
        self.assertEqual(code, 1)
        self.assertEqual(calls, ['build', 'deliver'])
        run.assert_not_called()
        self.assertIn('deliver failed', text)

if __name__ == '__main__':
    unittest.main()
