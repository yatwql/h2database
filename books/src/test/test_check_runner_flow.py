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
        for step in ('fast-gates', 'gates', 'tests', 'slow', 'deliver'):
            with self.subTest(step=step):
                command = self.runner._command(step)
                self.assertTrue(command)
                self.assertTrue(os.path.isabs(command[1]))

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
