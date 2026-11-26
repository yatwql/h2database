#!/usr/bin/env python3
"""test_report: collection without execution, the perf window, prune, last report.

The tool reads what the suite already wrote — TAGS in modules, the perf history,
report directories — so these cases build those inputs directly.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

TESTS_SUBDIR = ('src', 'test')


class TestReportToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'test_report')
        self.tests = os.path.join(self.root, *TESTS_SUBDIR)
        os.makedirs(self.tests, exist_ok=True)
        self.original_tests = self.mod.TESTS_DIR
        self.mod.__dict__['TESTS_DIR'] = self.tests
        self.addCleanup(self.mod.__dict__.__setitem__, 'TESTS_DIR', self.original_tests)

    def write_case(self, name: str, text: str) -> None:
        with open(os.path.join(self.tests, name), 'w', encoding='utf-8') as fh:
            fh.write(text)

    # -- collect ---------------------------------------------------------
    def test_collection_reads_tiers_from_the_tags(self):
        self.write_case('test_fast.py', "TAGS = ('layer:lib', 'tier:fast')\n\n"
                                        'class T(unittest.TestCase):\n'
                                        '    def test_a(self):\n        pass\n'
                                        '    def test_b(self):\n        pass\n')
        self.write_case('test_slow.py', "TAGS = ('layer:lib', 'tier:slow')\n\n"
                                        'def test_c():\n    pass\n')
        self.write_case('test_untiered.py', 'def test_d():\n    pass\n')
        self.write_case('test_no_cases.py', 'HELPER = 1\n')
        payload = self.mod.collect()
        self.assertEqual(payload['counts']['fast'], 2)
        self.assertEqual(payload['counts']['slow'], 1)
        self.assertEqual(payload['counts']['untiered'], 1)
        self.assertTrue(os.path.isfile(payload['path']))

    # -- perf window -----------------------------------------------------
    def history(self, runs: list[dict]) -> str:
        folder = os.path.join(self.root, 'logs')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, 'perf-history.jsonl')
        with open(path, 'w', encoding='utf-8') as fh:
            for run in runs:
                fh.write(json.dumps(run) + '\n')
            fh.write('not json\n')
        return path

    def test_one_run_is_not_enough_for_a_comparison(self):
        self.history([{'steps': [{'step': 'tests', 'seconds': 10}]}])
        payload = self.mod.perf_window()
        self.assertEqual(payload['steps'], [])
        self.assertEqual(payload['runs'], 1)

    def test_a_regressed_step_is_flagged(self):
        self.history([
            {'steps': [{'step': 'tests', 'seconds': 10.0}]},
            {'steps': [{'step': 'tests', 'seconds': 10.0}]},
            {'steps': [{'step': 'tests', 'seconds': 40.0}]},
        ])
        payload = self.mod.perf_window()
        step = payload['steps'][0]
        self.assertEqual(step['step'], 'tests')
        self.assertTrue(step['regressed'], step)

    def test_a_broken_step_entry_is_ignored(self):
        self.history([
            {'steps': ['oops', {'step': 'tests', 'seconds': 'x'}]},
            {'steps': [{'step': 'tests', 'seconds': 1.0}]},
        ])
        payload = self.mod.perf_window()
        # the unreadable entries contribute nothing; the readable run still shows
        self.assertEqual([step['step'] for step in payload['steps']], ['tests'])
        self.assertIsNone(payload['steps'][0]['median'])

    # -- prune -----------------------------------------------------------
    def report_dir(self, days_ago: int) -> str:
        stamp = (datetime.datetime.now() - datetime.timedelta(days=days_ago)).strftime('%Y%m%d-%H%M%S')
        path = os.path.join(self.mod.reports_root(), stamp)
        os.makedirs(path, exist_ok=True)
        return path

    def test_prune_drops_only_reports_past_the_window(self):
        old = self.report_dir(400)
        fresh = self.report_dir(0)
        with open(os.path.join(self.mod.reports_root(), 'not-a-stamp'), 'w',
                  encoding='utf-8') as fh:
            fh.write('')
        removed = self.mod.prune(dry_run=True)
        self.assertEqual(removed, [os.path.basename(old)])
        self.assertTrue(os.path.isdir(old), 'dry run must not delete')
        removed = self.mod.prune()
        self.assertEqual(removed, [os.path.basename(old)])
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.isdir(fresh))

    # -- last failures ---------------------------------------------------
    def report_with(self, cases: list[dict]) -> str:
        path = self.report_dir(0)
        with open(os.path.join(path, 'report.json'), 'w', encoding='utf-8') as fh:
            json.dump({'cases': cases}, fh)
        return path

    def test_a_report_without_failures_has_nothing_to_rerun(self):
        self.report_with([{'id': 'a::b', 'outcome': 'pass'}])
        payload = self.mod.last_failures()
        self.assertEqual(payload['failures'], [])
        self.assertEqual(payload['rerun'], '')

    def test_failures_produce_a_rerun_command_for_their_modules(self):
        self.report_with([{'id': 'test_x.T::test_a', 'outcome': 'fail'},
                          {'id': 'test_y.T::test_b', 'outcome': 'error'}])
        payload = self.mod.last_failures()
        self.assertEqual(len(payload['failures']), 2)
        self.assertIn('test_x.py', payload['rerun'])
        self.assertIn('test_y.py', payload['rerun'])

    def test_an_unreadable_report_reads_as_no_failures(self):
        path = self.report_dir(0)
        with open(os.path.join(path, 'report.json'), 'w', encoding='utf-8') as fh:
            fh.write('{broken')
        payload = self.mod.last_failures()
        self.assertEqual(payload['failures'], [])

    def test_without_any_report_the_tool_says_so(self):
        empty = os.path.join(self.tmp.name, 'empty-reports')
        os.makedirs(empty, exist_ok=True)
        with mock.patch.object(self.mod, 'reports_root', return_value=empty):
            payload = self.mod.last_failures()
        self.assertEqual(payload['report'], '')


if __name__ == '__main__':
    unittest.main()
