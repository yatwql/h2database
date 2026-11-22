#!/usr/bin/env python3
"""The health view reads the same numbers the gates read, and nothing else."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:audit', 'tier:fast')

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

COVERAGE_JSON = {
    'totals': {'percent_covered': 87.6, 'num_statements': 100, 'missing_lines': 12,
               'num_partial_branches': 9},
    'files': {
        'books/src/python/thin.py': {'summary': {'percent_covered': 50.0,
                                                 'num_statements': 20,
                                                 'num_partial_branches': 7,
                                                 'missing_lines': 10}},
        'books/src/python/tiny.py': {'summary': {'percent_covered': 0.0,
                                                 'num_statements': 2,
                                                 'num_partial_branches': 0,
                                                 'missing_lines': 2}},
    },
}


class TestHealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.health = _fixture.load_module(self.root, 'test_health')

    def run_json(self, mode: str = '--json'):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.health.main([mode] if mode else [])
        return code, buffer.getvalue()

    def test_coverage_snapshot_reads_the_json_and_skips_tiny_files(self):
        with mock.patch.object(self.health, '_run',
                               return_value=(0, json.dumps(COVERAGE_JSON))):
            snapshot = self.health.coverage_snapshot()
        self.assertEqual(snapshot['total_percent'], 87.6)
        self.assertEqual([item['file'] for item in snapshot['thinnest']],
                         ['books/src/python/thin.py'])
        self.assertEqual(snapshot['branch_heavy'][0]['half_branches'], 7)

    def test_an_unreadable_coverage_file_is_not_an_error(self):
        with mock.patch.object(self.health, '_run', return_value=(1, '')):
            self.assertEqual(self.health.coverage_snapshot(), {})
        with mock.patch.object(self.health, '_run', return_value=(0, 'not json')):
            self.assertEqual(self.health.coverage_snapshot(), {})

    def test_below_baseline_names_the_file_that_dropped(self):
        baseline = os.path.join(self.root, 'data', 'baselines', 'coverage.json')
        os.makedirs(os.path.dirname(baseline), exist_ok=True)
        with open(baseline, 'w', encoding='utf-8') as fh:
            json.dump({'files': {'books/src/python/thin.py': 90.0}}, fh)
        coverage = {'files': [{'file': 'books/src/python/thin.py', 'percent': 50.0}]}
        self.assertEqual(self.health.below_baseline(coverage),
                         [{'file': 'books/src/python/thin.py',
                           'baseline': 90.0, 'now': 50.0}])
        self.assertEqual(self.health.below_baseline({}), [])

    def test_long_functions_are_found_by_length(self):
        source = os.path.join(self.root, 'src', 'python')
        os.makedirs(source, exist_ok=True)
        body = 'def wide():\n' + ''.join(f'    x{i} = {i}\n' for i in range(70))
        with open(os.path.join(source, 'wide.py'), 'w', encoding='utf-8') as fh:
            fh.write(body)
        with mock.patch.object(self.health, 'PY_ROOT', source), \
                mock.patch.object(self.health, 'REPO_ROOT', self.root):
            found = self.health.long_functions(60)
        self.assertEqual([item['name'] for item in found], ['wide'])

    def test_the_report_prints_every_reading(self):
        with mock.patch.object(self.health, '_run',
                               return_value=(0, json.dumps(COVERAGE_JSON))), \
                mock.patch.object(self.health, 'long_functions',
                                  return_value=[{'file': 'a.py', 'name': 'wide', 'lines': 99}]), \
                mock.patch.object(self.health, 'loose_assertions', return_value=61):
            code, out = self.run_json()
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(payload['loose_assertions'], 61)
        self.assertEqual(payload['long_functions'][0]['lines'], 99)

    def test_the_table_names_the_thinnest_module(self):
        with mock.patch.object(self.health, '_run',
                               return_value=(0, json.dumps(COVERAGE_JSON))), \
                mock.patch.object(self.health, 'long_functions', return_value=[]), \
                mock.patch.object(self.health, 'loose_assertions', return_value=0):
            code, out = self.run_json('')
        self.assertEqual(code, 0)
        self.assertIn('books/src/python/thin.py', out)
        self.assertIn('松散断言', out)

    def test_no_coverage_data_says_so(self):
        with mock.patch.object(self.health, '_run', return_value=(1, '')), \
                mock.patch.object(self.health, 'long_functions', return_value=[]), \
                mock.patch.object(self.health, 'loose_assertions', return_value=-1):
            code, out = self.run_json('')
        self.assertEqual(code, 0)
        self.assertIn('无数据', out)
        self.assertIn('不可读', out)


if __name__ == '__main__':
    unittest.main()
