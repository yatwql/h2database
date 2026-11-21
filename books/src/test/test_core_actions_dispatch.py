#!/usr/bin/env python3
"""Core actions: dispatch, unknown actions, settings and the LLM bridge."""

from __future__ import annotations

import os
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

if __name__ == '__main__':
    unittest.main()
