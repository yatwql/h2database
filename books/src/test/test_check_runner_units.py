#!/usr/bin/env python3
"""Tier runner: step selection, timeouts, machine info and report files."""

from __future__ import annotations

import datetime
import json
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

    def test_report_paths_are_the_days_journal(self):
        log, summary = self.runner.report_paths(
            'p0', datetime.datetime(2026, 1, 1, 9, 52, 12))
        self.assertTrue(log.endswith('check-p0-2026-01-01.log'))
        self.assertTrue(summary.endswith('check-p0-2026-01-01.jsonl'))

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

    def test_a_run_records_the_tree_it_judged_and_where_it_sits(self):
        log_path = os.path.join(self.tmp.name, 'check-p0-2026-11-24.log')
        jsonl_path = os.path.join(self.tmp.name, 'check-p0-2026-11-24.jsonl')
        with mock.patch.object(self.runner, 'run_step',
                               return_value={'step': 'lint', 'code': 0, 'seconds': 0.1,
                                             'argv': ['ruff', 'check']}), \
                mock.patch.object(self.runner, 'report_paths',
                                  return_value=(log_path, jsonl_path)), \
                mock.patch.object(self.runner, 'book_root', return_value=self.tmp.name), \
                mock.patch('builtins.print'):
            summary = self.runner.run('p0', only='lint')
        self.assertTrue(summary['ok'])
        self.assertIn('commit', summary['git'])
        self.assertIn('dirty', summary['git'])
        self.assertTrue(summary['started_at'])
        self.assertEqual(summary['log_offset'], 0)
        self.assertGreater(summary['log_len'], 0)
        with open(jsonl_path, encoding='utf-8') as handle:
            record = json.loads(handle.read().strip().splitlines()[-1])
        self.assertEqual(record['steps'][0]['argv'], ['ruff', 'check'])
        self.assertIn('git', record)
        # one writer per fact: the journal and the summary, nothing else
        self.assertEqual(sorted(os.listdir(self.tmp.name)),
                         ['check-p0-2026-11-24.jsonl', 'check-p0-2026-11-24.log'])

    def test_two_runs_of_a_day_share_one_journal(self):
        """A day is the unit: the second run appends, it does not start a file."""
        log_path = os.path.join(self.tmp.name, 'check-p0-2026-11-24.log')
        jsonl_path = os.path.join(self.tmp.name, 'check-p0-2026-11-24.jsonl')
        with mock.patch.object(self.runner, 'run_step',
                               return_value={'step': 'lint', 'code': 0, 'seconds': 0.0}), \
                mock.patch.object(self.runner, 'report_paths',
                                  return_value=(log_path, jsonl_path)), \
                mock.patch('builtins.print'):
            self.runner.run('p0', only='lint')
            self.runner.run('p0', only='lint')
        for path in (log_path, jsonl_path):
            with open(path, encoding='utf-8') as handle:
                text = handle.read()
            self.assertEqual(text.count('mode=p0') if path.endswith('.log')
                             else len(text.strip().splitlines()), 2)
        self.assertEqual(sorted(os.listdir(self.tmp.name)),
                         ['check-p0-2026-11-24.jsonl', 'check-p0-2026-11-24.log'])

if __name__ == '__main__':
    unittest.main()
