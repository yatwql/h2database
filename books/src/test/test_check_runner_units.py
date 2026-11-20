#!/usr/bin/env python3
"""Tier runner: step selection, timeouts, machine info and report files."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

class RunnerUnitsTest(unittest.TestCase):
    def setUp(self):
        self.runner = _fixture.load_module(BOOK_ROOT, 'check_runner')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_only_restricts_and_preserves_order(self):
        steps = self.runner.select_steps(('lint', 'fast-gates', 'tests'),
                                         only='tests,lint')
        self.assertEqual(steps, ('lint', 'tests'))

    def test_skip_removes_steps(self):
        steps = self.runner.select_steps(('lint', 'fast-gates', 'tests'), skip='fast-gates')
        self.assertEqual(steps, ('lint', 'tests'))

    def test_unknown_step_in_a_tier_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.runner.select_steps(('lint',), only='deliver')

    def test_machine_info_carries_the_essentials(self):
        info = self.runner.machine_info()
        for key in ('python', 'platform', 'cpus', 'locale', 'book_root'):
            self.assertIn(key, info)

    def test_report_paths_are_stamped_and_separate(self):
        log, summary = self.runner.report_paths('p0', '2026-01-01_000000')
        self.assertTrue(log.endswith('.log'))
        self.assertTrue(summary.endswith('.json'))
        self.assertIn('check-p0-2026-01-01_000000', log)

    def test_lint_step_is_skipped_when_no_linter_exists(self):
        with mock.patch.object(self.runner.shutil, 'which', return_value=None), \
                mock.patch.object(self.runner.importlib.util, 'find_spec', return_value=None):
            self.assertIsNone(self.runner._command('lint'))

    def test_lint_step_prefers_the_pinned_ruff(self):
        """A ruff from PATH may be another version; the venv module wins."""
        with mock.patch.object(self.runner.importlib.util, 'find_spec', return_value=object()):
            command = self.runner._command('lint')
        self.assertEqual(command[:3], [self.runner.PY, '-m', 'ruff'])

    def test_a_step_timeout_is_reported_as_code_124(self):
        log = os.path.join(self.tmp.name, 'timeout.log')
        with mock.patch.object(self.runner.subprocess, 'run',
                               side_effect=self.runner.subprocess.TimeoutExpired('x', 1)):
            result = self.runner.run_step('tests', log, timeout=1)
        self.assertEqual(result['code'], 124)

    def test_run_writes_a_latest_pointer(self):
        written = {}
        log_path = os.path.join(self.tmp.name, 'x.log')
        json_path = os.path.join(self.tmp.name, 'x.json')

        def fake_write(path, text):
            written[path] = text

        with mock.patch.object(self.runner, 'run_step',
                               return_value={'step': 'lint', 'code': 0, 'seconds': 0.0}), \
                mock.patch.object(self.runner, 'report_paths',
                                  return_value=(log_path, json_path)), \
                mock.patch.object(self.runner._fsutil, 'write_text', side_effect=fake_write), \
                mock.patch('builtins.print'):
            summary = self.runner.run('p0', only='lint')
        self.assertTrue(summary['ok'])
        self.assertTrue(any(path.endswith('check-latest.json') for path in written))

if __name__ == '__main__':
    unittest.main()
