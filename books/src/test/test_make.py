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

    def test_a_started_step_announces_the_phase_and_nothing_else_on_success(self):
        # the start line is the only output a successful step produces: it tells the
        # operator which phase is running while the child may still be silent
        step = ('demo', 'render/to_html.py', (), 'build')
        with mock.patch.object(self.make, '_step_process', return_value=completed(0)):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                _name, code, _elapsed = self.make.run_step(step)
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue().strip(), '.. demo')

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
                mock.patch.object(self.make._config, 'missing_files',
                                  return_value=[], create=True), \
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



    def test_a_missing_optional_tool_is_reported_not_fatal(self):
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=None):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = self.make.doctor()
        self.assertIn('pandoc', buffer.getvalue())
        self.assertIn(code, (0, 1))



class MakeEdgePathsTest(unittest.TestCase):
    """The driver's failure paths: timeouts, drift, ratchet drops, dispatch."""

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

    def test_pin_drift_names_every_disagreement(self):
        import importlib.metadata

        def version(name):
            if name == 'ruff':
                raise importlib.metadata.PackageNotFoundError(name)
            return '9.9'

        with mock.patch.object(self.make, 'pinned_versions',
                               return_value={'ruff': '1.0', 'pytest': '2.0'}), \
                mock.patch('importlib.metadata.version', side_effect=version):
            drift = self.make.pin_drift()
        self.assertTrue(any('missing' in item for item in drift), drift)
        self.assertTrue(any('pytest 9.9' in item for item in drift), drift)

    def test_a_bad_timeout_setting_falls_back_to_the_default(self):
        with mock.patch.dict(self.make._config.POLICY,
                             {'toolchain': {'step_timeout_s': 'soon'}}):
            self.assertEqual(self.make.step_timeout('to_html'),
                             float(self.make.STEP_TIMEOUT_S))

    def test_a_timed_out_step_kills_the_group_and_reraises(self):
        proc = mock.Mock(pid=4321, returncode=0)
        proc.communicate.side_effect = [self.make.subprocess.TimeoutExpired('cmd', 1),
                                        ('', '')]
        with mock.patch.object(self.make.subprocess, 'Popen', return_value=proc), \
                mock.patch.object(self.make.os, 'killpg', side_effect=OSError('gone')), \
                self.assertRaises(self.make.subprocess.TimeoutExpired):
            self.make._step_process(['demo'], 1)
        proc.kill.assert_called_once()

    def test_the_suite_step_falls_back_to_unittest_discovery(self):
        with mock.patch.object(self.make.importlib.util, 'find_spec', return_value=None), \
                mock.patch.object(self.make, '_step_process',
                                  return_value=completed(0)) as step:
            name, code, _elapsed = self.make.run_step(('unittest', None, (), 'test'))
        self.assertEqual((name, code), ('unittest', 0))
        self.assertIn('unittest', step.call_args[0][0])

    def test_a_step_that_times_out_fails_with_124(self):
        step = ('demo', 'render/to_html.py', (), 'build')
        buffer = io.StringIO()
        with mock.patch.object(self.make, '_step_process',
                               side_effect=self.make.subprocess.TimeoutExpired('cmd', 1)), \
                redirect_stdout(buffer):
            name, code, _elapsed = self.make.run_step(step)
        self.assertEqual((name, code), ('demo', 124))
        self.assertIn('timeout', buffer.getvalue())

    def test_mutation_is_advisory_unless_strict(self):
        with mock.patch.object(self.make.subprocess, 'run', return_value=completed(1)):
            self.assertEqual(self.make.mutation(2, strict=False), 0)
            self.assertEqual(self.make.mutation(2, strict=True), 1)

    def test_doctor_flags_a_missing_chapter(self):
        buffer = io.StringIO()
        with mock.patch.object(self.make, 'pin_drift', return_value=[]), \
                mock.patch.dict(self.make.OPTIONAL_TOOLS, {}, clear=True), \
                mock.patch.object(self.make._config, 'missing_files',
                                  return_value=['ch9.md']), \
                redirect_stdout(buffer):
            self.assertEqual(self.make.doctor(), 1)
        self.assertIn('chapter gap', buffer.getvalue())

    def test_report_health_runs_the_debt_reader(self):
        with mock.patch.object(self.make.subprocess, 'run',
                               return_value=completed(0)) as run:
            self.assertEqual(self.make.report(['health']), 0)
        self.assertIn('test_health.py', run.call_args[0][0][-1])

    def test_coverage_reports_a_timeout_and_a_failed_run(self):
        buffer = io.StringIO()
        with mock.patch.object(self.make.subprocess, 'run',
                               side_effect=self.make.subprocess.TimeoutExpired('c', 1)), \
                redirect_stdout(buffer):
            self.assertEqual(self.make.coverage(), 2)
        with mock.patch.object(self.make.subprocess, 'run',
                               side_effect=[completed(1, out='boom', err='err'),
                                            completed(0)]), \
                redirect_stdout(buffer):
            self.assertEqual(self.make.coverage(), 1)

    def test_coverage_records_and_enforces_the_baseline(self):
        buffer = io.StringIO()
        with mock.patch.object(self.make, 'thin_files', return_value=[]), \
                mock.patch.object(self.make, 'coverage_ratchet',
                                  return_value=([], 'coverage.json')), \
                mock.patch.object(self.make.subprocess, 'run',
                                  return_value=completed(0)), \
                redirect_stdout(buffer):
            self.assertEqual(self.make.coverage(update_baseline=True), 0)
        self.assertIn('coverage baseline written', buffer.getvalue())
        with mock.patch.object(self.make, 'thin_files', return_value=[]), \
                mock.patch.object(self.make, 'coverage_ratchet',
                                  return_value=([('src/a.py', 90.0, 80.0)], 'coverage.json')), \
                mock.patch.object(self.make.subprocess, 'run',
                                  return_value=completed(0)), \
                redirect_stdout(buffer):
            self.assertEqual(self.make.coverage(), 1)
        self.assertIn('per-file coverage dropped', buffer.getvalue())

    def test_thin_files_survives_a_broken_coverage_json(self):
        with mock.patch.object(self.make.subprocess, 'run', side_effect=OSError('nope')):
            self.assertEqual(self.make.thin_files(50), [])

    def test_the_coverage_payload_defaults_to_empty(self):
        with mock.patch.object(self.make.subprocess, 'run',
                               return_value=completed(0, out='not json')):
            self.assertEqual(self.make._coverage_json(), {})

    def test_percentages_skip_a_module_too_small_to_judge(self):
        payload = {'files': {'a.py': {'summary': {'num_statements': 3,
                                                  'percent_covered': 0.0}},
                             'b.py': {'summary': {'num_statements': 30,
                                                  'percent_covered': 91.27}}}}
        self.assertEqual(self.make._percentages(payload), {'b.py': 91.3})

    def test_an_unreadable_baseline_file_is_not_a_drop(self):
        path = os.path.join(self.root, self.make.COVERAGE_BASELINE_REL)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('{"files": {}}')
        with mock.patch.object(self.make, '_coverage_json', return_value={}), \
                mock.patch.object(self.make._fsutil, 'load_json',
                                  side_effect=ValueError('rot')):
            drops, reported = self.make.coverage_ratchet()
        self.assertEqual(drops, [])
        self.assertEqual(reported, path)

    def test_timings_print_each_step(self):
        buffer = io.StringIO()
        with mock.patch.object(self.make, '_select',
                               return_value=[('demo', 'x', (), 'build')]), \
                mock.patch.object(self.make, 'run_step',
                                  return_value=('demo', 0, 1.5)), \
                redirect_stdout(buffer):
            self.assertEqual(self.make._run_steps(self.args(timings=True)), 0)
        self.assertIn('ok   demo', buffer.getvalue())

    def test_main_dispatches_cover_and_mutation(self):
        with mock.patch.object(self.make, 'coverage', return_value=0) as covered, \
                mock.patch.object(self.make, 'mutation', return_value=0) as mutated:
            self.assertEqual(self.make.main(['cover']), 0)
            self.assertEqual(self.make.main(['mutation']), 0)
        covered.assert_called_once()
        mutated.assert_called_once()


class MakeEnvironmentTest(unittest.TestCase):
    """The interpreter guard, the pins and the CLI's remaining edges."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.make = _fixture.load_module(self.root, 'make')

    def test_venv_python_is_found_under_the_book(self):
        candidate = os.path.join(self.root, '.venv', 'bin', 'python')
        os.makedirs(os.path.dirname(candidate), exist_ok=True)
        open(candidate, 'w').close()
        with mock.patch.object(self.make, 'book_root', lambda: self.root):
            self.assertEqual(self.make.venv_python(), os.path.normpath(candidate))

    def test_the_interpreter_guard_speaks_only_when_it_must(self):
        make = self.make
        self.assertIsNone(make.interpreter_problem(None, '/usr/bin/python3'))
        with mock.patch.dict(os.environ, {'BOOK_ALLOW_SYSTEM_PYTHON': '1'}):
            self.assertIsNone(make.interpreter_problem('/project/.venv', '/usr/bin/python3'))
        self.assertIsNone(make.interpreter_problem('/x/python', '/x/python'))
        self.assertIn('not the project virtualenv',
                      make.interpreter_problem('/x/python', '/usr/bin/python3') or '')

    def test_the_guard_refuses_a_system_interpreter(self):
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=False) as env:
            env.pop('BOOK_ALLOW_SYSTEM_PYTHON', None)
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                self.make.enforce_venv('/x/python', '/usr/bin/python3')
        self.assertEqual(raised.exception.code, 3)
        self.assertIn('override', stderr.getvalue())

    def test_pins_are_read_from_requirements(self):
        with open(os.path.join(self.root, 'requirements.txt'), 'w', encoding='utf-8') as handle:
            handle.write('# pinned\nruff==0.5.1  # lint\nno-pin\npytest_extras==2.0\n')
        pins = self.make.pinned_versions()
        self.assertEqual(pins['ruff'], '0.5.1')
        self.assertEqual(pins['pytest-extras'], '2.0')
        self.assertNotIn('no-pin', pins)

    def test_a_step_that_finishes_returns_its_streams(self):
        proc = mock.Mock(pid=1, returncode=0)
        proc.communicate.return_value = ('out', 'err')
        with mock.patch.object(self.make.subprocess, 'Popen', return_value=proc):
            result = self.make._step_process(['demo'], 5)
        self.assertEqual((result.returncode, result.stdout), (0, 'out'))

    def test_doctor_confirms_a_matching_venv(self):
        buffer = io.StringIO()
        with mock.patch.object(self.make, 'venv_python', return_value=sys.executable), \
                mock.patch.object(self.make, 'pin_drift', return_value=[]), \
                mock.patch.dict(self.make.OPTIONAL_TOOLS, {}, clear=True), \
                mock.patch.object(self.make._config, 'missing_files',
                                  return_value=[], create=True), \
                redirect_stdout(buffer):
            self.assertEqual(self.make.doctor(), 0)
        self.assertIn('venv        : ok', buffer.getvalue())

    def test_an_unknown_edition_is_a_usage_error(self):
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {'BOOK_EDITION': 'nope'}):
            with redirect_stderr(stderr):
                self.assertEqual(self.make.main(['check']), 2)
        self.assertIn('error:', stderr.getvalue())

    def test_an_explicit_edition_reaches_the_environment(self):
        args = self.make._parser().parse_args(['check', '--edition', 'v2'])
        previous = os.environ.pop('BOOK_EDITION', None)
        self.addCleanup(self.restore_edition, previous)
        self.make._apply_selection(args)
        self.assertEqual(os.environ.get('BOOK_EDITION'), 'v2')

    def restore_edition(self, previous: str | None) -> None:
        if previous is None:
            os.environ.pop('BOOK_EDITION', None)
        else:
            os.environ['BOOK_EDITION'] = previous

    def test_main_dispatches_doctor(self):
        with mock.patch.object(self.make, 'doctor', return_value=0) as doctor:
            self.assertEqual(self.make.main(['doctor']), 0)
        doctor.assert_called_once()

    def test_the_entry_point_runs_the_driver(self):
        with mock.patch.dict(os.environ, {'BOOK_ALLOW_SYSTEM_PYTHON': '1'}):
            code, out = _fixture.run_inproc(self.root, 'make.py', '--help')
        self.assertEqual(code, 0, out[-300:])

if __name__ == '__main__':
    unittest.main()
