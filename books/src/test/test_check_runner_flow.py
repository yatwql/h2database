#!/usr/bin/env python3
"""Tier runner: step commands, failure reporting and main's flags."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

class StepCommandTest(unittest.TestCase):
    def setUp(self):
        self.runner = _fixture.load_module(BOOK_ROOT, 'check_runner')

    def test_every_step_maps_to_a_command(self):
        for step in ('fast-gates', 'gates', 'slow', 'deliver'):
            with self.subTest(step=step):
                command = self.runner._command(step)
                self.assertTrue(command)
                self.assertTrue(os.path.isabs(command[1]))

    def test_the_tests_step_delegates_to_the_test_command(self):
        command = self.runner._command('tests', 'tier_fast')
        self.assertEqual(command, self.runner.tests_command('tier_fast'))

    def test_gates_step_keeps_going(self):
        self.assertIn('--keep-going', self.runner._command('gates'))

    def test_slow_and_deliver_select_their_make_commands(self):
        self.assertIn('--full', self.runner._command('slow'))
        self.assertIn('deliver', self.runner._command('deliver'))

    def test_unknown_step_raises(self):
        with self.assertRaises(KeyError):
            self.runner._command('nope')

class RunStepTest(unittest.TestCase):
    def setUp(self):
        self.runner = _fixture.load_module(BOOK_ROOT, 'check_runner')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = os.path.join(self.tmp.name, 'run.log')

    def test_a_failing_step_prints_the_tail(self):
        failure = mock.Mock(returncode=1, stdout='line1\nline2\nboom\n', stderr='')
        buffer = io.StringIO()
        with mock.patch.object(self.runner.subprocess, 'run', return_value=failure), \
                redirect_stdout(buffer):
            result = self.runner.run_step('tests', self.log)
        self.assertEqual(result['code'], 1)
        self.assertIn('boom', buffer.getvalue())

    def test_a_skipped_step_reports_the_reason(self):
        with mock.patch.object(self.runner, '_command', return_value=None):
            result = self.runner.run_step('lint', self.log)
        self.assertEqual(result['code'], 0)
        self.assertIn('skipped', result)

    def test_the_slow_step_sets_the_slow_flag(self):
        seen = {}

        def fake_run(command, **kwargs):
            seen.update(kwargs.get('env') or {})
            return mock.Mock(returncode=0, stdout='', stderr='')

        with mock.patch.object(self.runner.subprocess, 'run', side_effect=fake_run), \
                redirect_stdout(io.StringIO()):
            self.runner.run_step('slow', self.log)
        self.assertEqual(seen.get('BOOK_SLOW'), '1')

    def test_the_run_log_records_the_step(self):
        ok = mock.Mock(returncode=0, stdout='out\n', stderr='')
        with mock.patch.object(self.runner.subprocess, 'run', return_value=ok), \
                redirect_stdout(io.StringIO()):
            self.runner.run_step('tests', self.log)
        with open(self.log, encoding='utf-8') as fh:
            self.assertIn('tests', fh.read())

class MarkerSelectionTest(unittest.TestCase):
    """The tier decides which tests run, via pytest marker expressions."""

    def setUp(self):
        self.runner = _fixture.load_module(BOOK_ROOT, 'check_runner')

    def test_each_tier_declares_a_marker_expression(self):
        self.assertEqual(self.runner.MODE_MARKERS['p0'], 'tier_fast')
        self.assertEqual(self.runner.MODE_MARKERS['p1'], 'not tier_slow')
        self.assertEqual(self.runner.MODE_MARKERS['p2'], '')

    def test_pytest_command_carries_the_marker(self):
        command = self.runner.tests_command('tier_fast')
        self.assertIn('-m', command)
        self.assertEqual(command[-1], 'tier_fast')

    def test_pytest_command_without_a_marker_runs_everything(self):
        command = self.runner.tests_command('')
        # `-m pytest` is python's module switch; no marker expression follows it
        self.assertEqual(command.count('-m'), 1)

    def test_unittest_is_used_when_pytest_is_missing(self):
        with mock.patch.object(self.runner.importlib.util, 'find_spec',
                               return_value=None):
            command = self.runner.tests_command('tier_fast')
        self.assertIn('make.py', command[1])
        self.assertIn('test', command)

    def test_run_passes_the_tier_marker_to_the_steps(self):
        seen = []

        def fake_step(step, log_path, timeout=0, marker=''):
            seen.append((step, marker))
            return {'step': step, 'code': 0, 'seconds': 0.0}

        with mock.patch.object(self.runner, 'run_step', side_effect=fake_step), \
                mock.patch.object(self.runner, 'report_paths',
                                  return_value=(os.path.join(tempfile.gettempdir(), 'a.log'),
                                                os.path.join(tempfile.gettempdir(), 'a.json'))), \
                mock.patch.object(self.runner._fsutil, 'write_text'), \
                mock.patch('builtins.print'):
            summary = self.runner.run('p0', only='tests')
        self.assertEqual(seen, [('tests', 'tier_fast')])
        self.assertEqual(summary['marker'], 'tier_fast')

    def test_explicit_marker_overrides_the_tier_default(self):
        seen = []

        def fake_step(step, log_path, timeout=0, marker=''):
            seen.append(marker)
            return {'step': step, 'code': 0, 'seconds': 0.0}

        with mock.patch.object(self.runner, 'run_step', side_effect=fake_step), \
                mock.patch.object(self.runner, 'report_paths',
                                  return_value=(os.path.join(tempfile.gettempdir(), 'b.log'),
                                                os.path.join(tempfile.gettempdir(), 'b.json'))), \
                mock.patch.object(self.runner._fsutil, 'write_text'), \
                mock.patch('builtins.print'):
            self.runner.run('p0', only='tests', marker='layer_audit')
        self.assertEqual(seen, ['layer_audit'])

    def test_main_forwards_the_marker_flag(self):
        with mock.patch.object(self.runner, 'run',
                               return_value={'ok': True, 'mode': 'p0'}) as run, \
                redirect_stdout(io.StringIO()):
            self.runner.main(['--marker', 'edge'])
        self.assertEqual(run.call_args.kwargs['marker'], 'edge')


class MainFlagsTest(unittest.TestCase):
    def setUp(self):
        self.runner = _fixture.load_module(BOOK_ROOT, 'check_runner')

    def test_only_and_skip_reach_the_run(self):
        with mock.patch.object(self.runner, 'run',
                               return_value={'ok': True, 'mode': 'p0'}) as run, \
                redirect_stdout(io.StringIO()):
            self.runner.main(['--mode', 'p0', '--only', 'lint', '--skip', 'tests',
                              '--timeout', '5'])
        kwargs = run.call_args.kwargs
        self.assertEqual((kwargs['only'], kwargs['skip'], kwargs['timeout']),
                         ('lint', 'tests', 5.0))

    def test_no_archive_is_forwarded(self):
        with mock.patch.object(self.runner, 'run',
                               return_value={'ok': True, 'mode': 'p0'}) as run, \
                redirect_stdout(io.StringIO()):
            self.runner.main(['--no-archive'])
        self.assertFalse(run.call_args.kwargs['archive'])

    def test_a_failed_run_returns_one(self):
        with mock.patch.object(self.runner, 'run',
                               return_value={'ok': False, 'mode': 'p0',
                                             'failed_step': 'tests', 'seconds': 1.0}), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.runner.main([]), 1)

if __name__ == '__main__':
    unittest.main()
