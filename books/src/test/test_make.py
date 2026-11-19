#!/usr/bin/env python3
"""Tests for the make.py driver (steps, doctor, coverage gate, CLI)."""
from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _fixture

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


def completed(code: int = 0, out: str = '', err: str = ''):
    result = mock.Mock()
    result.returncode = code
    result.stdout = out
    result.stderr = err
    return result


class SelectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.make = _fixture.load_module(self.root, 'make')

    def args(self, **kwargs) -> argparse.Namespace:
        base = {'command': 'check', 'only': None, 'skip': None,
                'timings': False, 'keep_going': False, 'full': False}
        base.update(kwargs)
        return argparse.Namespace(**base)

    def test_group_steps_are_selected(self):
        steps = self.make._select(self.args(command='build'))
        self.assertEqual([name for name, *_ in steps], list(self.make.GROUPS['build']))

    def test_only_and_skip_narrow_the_selection(self):
        steps = self.make._select(self.args(command='build', only='to_html,to_pdf',
                                            skip='to_pdf'))
        self.assertEqual([name for name, *_ in steps], ['to_html'])

    def test_unknown_step_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.make._select(self.args(only='nopy'))

    def test_test_command_runs_the_suite(self):
        steps = self.make._select(self.args(command='test'))
        self.assertEqual(steps[0][0], 'unittest')

    def test_run_step_reports_failures(self):
        step = ('demo', 'render/to_html.py', (), 'build')
        failure = completed(1, out='boom\n', err='err\n')
        with mock.patch.object(self.make.subprocess, 'run', return_value=failure):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                name, code, elapsed = self.make.run_step(step)
        self.assertEqual((name, code), ('demo', 1))
        self.assertGreaterEqual(elapsed, 0.0)
        self.assertIn('FAIL demo', buffer.getvalue())

    def test_run_step_success_prints_nothing(self):
        step = ('demo', 'render/to_html.py', (), 'build')
        with mock.patch.object(self.make.subprocess, 'run', return_value=completed(0)):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                _name, code, _elapsed = self.make.run_step(step)
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue(), '')

    def test_doctor_reports_missing_tools(self):
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=None), \
                mock.patch.object(self.make.subprocess, 'run', return_value=completed(0)):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = self.make.doctor()
        self.assertEqual(code, 1)
        self.assertIn('MISSING', buffer.getvalue())

    def test_doctor_passes_when_everything_is_present(self):
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=True), \
                mock.patch.object(self.make.subprocess, 'run',
                                  return_value=completed(0, out='/usr/bin/pandoc\n')), \
                mock.patch.object(self.make._config, 'missing_files', return_value=[]), \
                redirect_stdout(io.StringIO()):
            code = self.make.doctor()
        self.assertEqual(code, 0)

    def test_coverage_without_the_module(self):
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=None), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.make.coverage(), 2)

    def test_coverage_enforces_the_threshold(self):
        buffer = io.StringIO()
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=True), \
                mock.patch.object(self.make.subprocess, 'run',
                                  side_effect=[completed(0), completed(1)]), \
                redirect_stdout(buffer):
            self.assertEqual(self.make.coverage(), 1)
        self.assertIn('FAIL', buffer.getvalue())

    def test_main_report_forwards_its_own_arguments(self):
        with mock.patch.object(self.make.subprocess, 'run', return_value=completed(0)) as run:
            self.assertEqual(self.make.main(['report', '--json']), 0)
        self.assertIn('--json', run.call_args[0][0])

    def test_report_delegates_to_the_scorecard(self):
        with mock.patch.object(self.make.subprocess, 'run', return_value=completed(0)) as run:
            self.assertEqual(self.make.report(['--json']), 0)
        self.assertIn('scorecard.py', ' '.join(run.call_args[0][0]))

    def test_main_runs_steps_and_stops_on_failure(self):
        with mock.patch.object(self.make.subprocess, 'run', return_value=completed(1)), \
                redirect_stdout(io.StringIO()):
            code = self.make.main(['build', '--only', 'to_html'])
        self.assertEqual(code, 1)

    def test_main_keep_going_counts_every_failure(self):
        with mock.patch.object(self.make.subprocess, 'run', return_value=completed(1)), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = self.make.main(['build', '--only', 'to_html,to_pdf',
                                   '--keep-going', '--timings'])
        self.assertEqual(code, 1)

    def test_main_full_flips_the_slow_flag(self):
        with mock.patch.object(self.make.subprocess, 'run', return_value=completed(0)), \
                mock.patch.dict(os.environ, {}, clear=False):
            with redirect_stdout(io.StringIO()):
                self.make.main(['test', '--full'])
            self.assertEqual(os.environ.get('BOOK_SLOW'), '1')
        os.environ.pop('BOOK_SLOW', None)

    def test_main_with_nothing_selected(self):
        with redirect_stdout(io.StringIO()) as buffer:
            code = self.make.main(['build', '--only', 'to_html', '--skip', 'to_html'])
        self.assertEqual(code, 0)
        self.assertIn('nothing to do', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
