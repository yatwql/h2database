#!/usr/bin/env python3
"""Failure extraction: a long run log becomes a short failure list."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

TAGS = ('layer:audit', 'tier:fast')

LOG = """=== check p0 (commit gate): 3 step(s) ===
  ok   lint (0.5s)
FAIL: test_runs (test_demo.WidgetTest)
AssertionError: 1 != 2
ERROR: test_missing (test_demo.OtherTest)
FileNotFoundError: [Errno 2] no such file
  FAIL tests (rc=1, 3.2s)
"""


class FailureExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, 'failure_extract')

    def log(self, text: str = LOG) -> str:
        path = os.path.join(self.tmp.name, 'run.log')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def test_failures_are_extracted_with_their_reason(self):
        failures = self.mod.parse(LOG)
        self.assertEqual([f['name'] for f in failures], ['test_runs', 'test_missing'])
        self.assertEqual(failures[0]['class'], 'WidgetTest')
        self.assertIn('1 != 2', failures[0]['reason'])
        self.assertIn('FileNotFoundError', failures[1]['reason'])

    def test_subtest_parameters_are_captured(self):
        text = ('FAIL: test_lang (test_demo.LangTest) (language=rust)\n'
                'AssertionError: boom\n')
        failures = self.mod.parse(text)
        self.assertEqual(failures[0]['subtest'], {'language': 'rust'})

    def test_a_clean_log_yields_nothing(self):
        self.assertEqual(self.mod.parse('  ok   lint (0.5s)\n'), [])

    def test_main_reads_a_file_and_exits_one(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([self.log()])
        self.assertEqual(code, 1)
        self.assertIn('WidgetTest.test_runs', buffer.getvalue())

    def test_main_json_reports_the_count(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([self.log(), '--json'])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload['count'], 2)

    def test_main_summary_lists_only_names(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([self.log(), '--summary'])
        self.assertEqual(code, 1)
        self.assertNotIn('AssertionError', buffer.getvalue())

    def test_a_missing_log_exits_two(self):
        with redirect_stdout(io.StringIO()):
            code = self.mod.main([os.path.join(self.tmp.name, 'none.log')])
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()
