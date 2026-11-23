#!/usr/bin/env python3
"""Tests for the make.py driver (steps, doctor, coverage gate, CLI)."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

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

class MakeDriverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.make = _fixture.load_module(self.root, 'make')

    def args(self, **kwargs) -> argparse.Namespace:
        base = {'command': 'check', 'only': None, 'skip': None,
                'timings': False, 'keep_going': False, 'full': False,
                'update_baseline': False}
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
        with mock.patch.object(self.make, '_step_process', return_value=failure):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                name, code, elapsed = self.make.run_step(step)
        self.assertEqual((name, code), ('demo', 1))
        self.assertGreaterEqual(elapsed, 0.0)
        self.assertIn('FAIL demo', buffer.getvalue())

    def test_run_step_success_prints_nothing(self):
        step = ('demo', 'render/to_html.py', (), 'build')
        with mock.patch.object(self.make, '_step_process', return_value=completed(0)):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                _name, code, _elapsed = self.make.run_step(step)
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue(), '')

    def test_doctor_reports_missing_tools(self):
        # doctor probes optional tools through find_spec and shutil.which, so both
        # must be stubbed or the test result depends on the machine
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=None), \
                mock.patch.object(self.make.shutil, 'which', return_value=None), \
                mock.patch.object(self.make, '_step_process', return_value=completed(0)):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = self.make.doctor()
        self.assertEqual(code, 1)
        self.assertIn('MISSING', buffer.getvalue())

    def test_doctor_passes_when_everything_is_present(self):
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=True), \
                mock.patch.object(self.make.shutil, 'which',
                                  return_value='/usr/bin/pandoc'), \
                mock.patch.object(self.make._config, 'missing_files', return_value=[]), \
                redirect_stdout(io.StringIO()):
            code = self.make.doctor()
        self.assertEqual(code, 0)

    def keep_the_active_book(self) -> None:
        """--book rebinds the process; put the previous binding back afterwards."""
        previous = self.make._config.current()
        previous_env = os.environ.get('BOOK_ROOT')
        self.addCleanup(self.make._config.reset, previous)
        self.addCleanup(self.restore_env, previous_env)

    def restore_env(self, value: str | None) -> None:
        if value is None:
            os.environ.pop('BOOK_ROOT', None)
        else:
            os.environ['BOOK_ROOT'] = value

    def test_an_explicit_book_without_book_toml_exits_two_before_any_step(self):
        empty = os.path.join(self.tmp.name, 'not-a-book')
        os.makedirs(empty, exist_ok=True)
        self.keep_the_active_book()
        err = io.StringIO()
        with mock.patch.object(self.make, 'run_step') as step, \
                redirect_stderr(err):
            code = self.make.main(['check', '--book', empty])
        self.assertEqual(code, 2)
        self.assertIn('book.toml', err.getvalue())
        step.assert_not_called()

    def test_an_explicit_book_rebinds_the_active_one(self):
        other = _fixture.build_book(os.path.join(self.tmp.name, 'second'))
        self.keep_the_active_book()
        with mock.patch.object(self.make, 'run_step', return_value=('x', 0, 0.0)), \
                redirect_stdout(io.StringIO()):
            code = self.make.main(['check', '--book', other])
        self.assertEqual(code, 0)
        self.assertEqual(self.make.book_root(), os.path.abspath(other))

    def test_coverage_without_the_module(self):
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=None), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.make.coverage(), 2)

    def test_coverage_enforces_the_threshold(self):
        buffer = io.StringIO()
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=True), \
                mock.patch.object(self.make.subprocess, 'run',
                                  side_effect=[completed(0), completed(1),
                                               completed(0, out='{}'),
                                               completed(0, out='{}')]), \
                redirect_stdout(buffer):
            self.assertEqual(self.make.coverage(), 1)
        self.assertIn('FAIL', buffer.getvalue())

    def test_a_thin_file_fails_the_coverage_gate(self):
        buffer = io.StringIO()
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=True), \
                mock.patch.object(self.make.subprocess, 'run',
                                  side_effect=[completed(0), completed(0),
                                               completed(0, out='{}'),
                                               completed(0, out='{}')]), \
                mock.patch.object(self.make, 'thin_files',
                                  return_value=[('books/src/python/x.py', 12)]), \
                redirect_stdout(buffer):
            self.assertEqual(self.make.coverage(), 1)
        self.assertIn('per-file floor', buffer.getvalue())

    def _cover(self, *, slow_env: str = '', **kwargs):
        """Drive coverage() with a recording subprocess.run and return the commands."""
        calls = []

        def run(command, **inner):
            calls.append(command)
            return completed(0, out='{}')

        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=True), \
                mock.patch.object(self.make.subprocess, 'run', side_effect=run), \
                mock.patch.dict(os.environ, {'BOOK_SLOW': slow_env}), \
                redirect_stdout(io.StringIO()):
            self.make.coverage(**kwargs)
        return calls[0]

    def test_coverage_default_measures_the_fast_tier_only(self):
        self.assertIn('tier_fast', self._cover())

    def test_coverage_full_measures_the_slow_tier_too(self):
        self.assertNotIn('tier_fast', self._cover(full=True))

    def test_coverage_follows_book_slow_from_the_environment(self):
        self.assertNotIn('tier_fast', self._cover(slow_env='1'))

    def test_thin_files_reads_the_coverage_json(self):
        payload = json.dumps({'files': {
            'books/src/python/thin.py': {'summary': {'num_statements': 20,
                                                     'percent_covered': 10.0}},
            'books/src/python/ok.py': {'summary': {'num_statements': 20,
                                                   'percent_covered': 95.0}},
            'books/src/python/tiny.py': {'summary': {'num_statements': 2,
                                                     'percent_covered': 0.0}}}})
        with mock.patch.object(self.make.subprocess, 'run',
                               return_value=completed(0, out=payload)):
            self.assertEqual(self.make.thin_files(60),
                             [('books/src/python/thin.py', 10)])

    def _ratchet_payload(self, values: dict) -> str:
        return json.dumps({'files': {name: {'summary': {'num_statements': 20,
                                                       'percent_covered': pct}}
                                     for name, pct in values.items()}})

    def test_coverage_baseline_records_every_file(self):
        payload = self._ratchet_payload({'books/src/python/a.py': 90.0})
        with mock.patch.object(self.make.subprocess, 'run',
                               return_value=completed(0, out=payload)):
            drops, path = self.make.coverage_ratchet(update=True)
        self.assertEqual(drops, [])
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding='utf-8') as fh:
            self.assertIn('books/src/python/a.py', json.load(fh)['files'])

    def test_a_file_below_its_baseline_is_reported(self):
        self._ratchet_payload({'books/src/python/a.py': 90.0})
        with mock.patch.object(self.make.subprocess, 'run',
                               return_value=completed(0, out=self._ratchet_payload(
                                   {'books/src/python/a.py': 90.0}))):
            self.make.coverage_ratchet(update=True)
        with mock.patch.object(self.make.subprocess, 'run',
                               return_value=completed(0, out=self._ratchet_payload(
                                   {'books/src/python/a.py': 77.5}))):
            drops, _ = self.make.coverage_ratchet()
        self.assertEqual(drops, [('books/src/python/a.py', 90.0, 77.5)])

    def test_a_rising_file_does_not_lower_the_baseline(self):
        with mock.patch.object(self.make.subprocess, 'run',
                               return_value=completed(0, out=self._ratchet_payload(
                                   {'books/src/python/a.py': 50.0}))):
            self.make.coverage_ratchet(update=True)
        with mock.patch.object(self.make.subprocess, 'run',
                               return_value=completed(0, out=self._ratchet_payload(
                                   {'books/src/python/a.py': 60.0}))):
            drops, _ = self.make.coverage_ratchet()
        self.assertEqual(drops, [])

    def test_main_report_forwards_its_own_arguments(self):
        with mock.patch.object(self.make.subprocess, 'run', return_value=completed(0)) as run:
            self.assertEqual(self.make.main(['report', '--json']), 0)
        self.assertIn('--json', run.call_args[0][0])

    def test_report_delegates_to_the_scorecard(self):
        with mock.patch.object(self.make.subprocess, 'run', return_value=completed(0)) as run:
            self.assertEqual(self.make.report(['--json']), 0)
        self.assertIn('scorecard.py', ' '.join(run.call_args[0][0]))

    def test_main_runs_steps_and_stops_on_failure(self):
        with mock.patch.object(self.make, '_step_process', return_value=completed(1)), \
                redirect_stdout(io.StringIO()):
            code = self.make.main(['build', '--only', 'to_html'])
        self.assertEqual(code, 1)

    def test_main_keep_going_counts_every_failure(self):
        with mock.patch.object(self.make, '_step_process', return_value=completed(1)), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = self.make.main(['build', '--only', 'to_html,to_pdf',
                                   '--keep-going', '--timings'])
        self.assertEqual(code, 1)

    def test_main_full_flips_the_slow_flag(self):
        with mock.patch.object(self.make, '_step_process', return_value=completed(0)), \
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
