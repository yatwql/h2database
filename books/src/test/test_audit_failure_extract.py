#!/usr/bin/env python3
"""Failure extraction: a long run log becomes a short failure list."""

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

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

TAGS = ("layer:audit", "tier:fast")

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
        self.mod = _fixture.load_module(BOOK_ROOT, "failure_extract")

    def log(self, text: str = LOG) -> str:
        path = os.path.join(self.tmp.name, "run.log")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_failures_are_extracted_with_their_reason(self):
        failures = self.mod.parse(LOG)
        self.assertEqual([f["name"] for f in failures], ["test_runs", "test_missing"])
        self.assertEqual(failures[0]["class"], "WidgetTest")
        self.assertIn("1 != 2", failures[0]["reason"])
        self.assertIn("FileNotFoundError", failures[1]["reason"])

    def test_subtest_parameters_are_captured(self):
        text = "FAIL: test_lang (test_demo.LangTest) (language=rust)\nAssertionError: boom\n"
        failures = self.mod.parse(text)
        self.assertEqual(failures[0]["subtest"], {"language": "rust"})

    def test_a_clean_log_yields_nothing(self):
        self.assertEqual(self.mod.parse("  ok   lint (0.5s)\n"), [])

    def test_main_reads_a_file_and_exits_one(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([self.log()])
        self.assertEqual(code, 1)
        self.assertIn("WidgetTest.test_runs", buffer.getvalue())

    def test_main_json_reports_the_count(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([self.log(), "--json"])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["count"], 2)

    def test_main_summary_lists_only_names(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([self.log(), "--summary"])
        self.assertEqual(code, 1)
        self.assertNotIn("AssertionError", buffer.getvalue())

    def test_a_missing_log_exits_two(self):
        with redirect_stdout(io.StringIO()):
            code = self.mod.main([os.path.join(self.tmp.name, "none.log")])
        self.assertEqual(code, 2)

    def test_without_a_log_argument_the_text_comes_from_stdin(self):
        buffer = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(LOG)), redirect_stdout(buffer):
            code = self.mod.main([])
        self.assertEqual(code, 1)
        self.assertIn("失败用例 2 个", buffer.getvalue())

    def test_a_log_without_failures_exits_clean(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([self.log("  ok   lint (0.5s)\n")])
        self.assertEqual(code, 0)
        self.assertIn("日志中没有失败用例", buffer.getvalue())

    def test_a_failure_without_a_reason_prints_only_its_name(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([self.log("FAIL: test_runs (test_demo.WidgetTest)\n")])
        self.assertEqual(code, 1)
        self.assertIn("WidgetTest.test_runs", buffer.getvalue())
        self.assertEqual(len(buffer.getvalue().splitlines()), 2)

    def test_the_script_entrypoint_reads_the_log_named_on_the_command_line(self):
        code, out = _fixture.run_inproc(BOOK_ROOT, "failure_extract.py", self.log())
        self.assertEqual(code, 1, out)


if __name__ == "__main__":
    unittest.main()
