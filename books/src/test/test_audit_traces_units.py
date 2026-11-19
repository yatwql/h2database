#!/usr/bin/env python3
"""Traces gate: both scopes, pattern classes, exemptions and CLI."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class TracesUnitTest(unittest.TestCase):
    def setUp(self):
        self.traces = _fixture.load_module(BOOK_ROOT, 'traces')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def doc(self, text: str) -> str:
        path = os.path.join(self.tmp.name, 'doc.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def scan_docs(self, text: str) -> list[dict]:
        path = self.doc(text)
        with mock.patch.object(self.traces, 'doc_files', return_value=[path]):
            return self.traces.scan_docs()

    # -- documentation scope ---------------------------------------------
    def test_review_round_is_reported(self):
        findings = self.scan_docs('本文经过第 3 轮评审。\n')
        self.assertEqual(findings[0]['kind'], 'review-round')

    def test_batch_and_relative_time_are_reported(self):
        kinds = {f['kind'] for f in self.scan_docs('第 2 批改动；本轮新增。\n')}
        self.assertIn('batch', kinds)
        self.assertIn('relative-time', kinds)

    def test_changelog_is_exempt(self):
        path = os.path.join(self.tmp.name, 'changelog.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('第 3 轮\n')
        with mock.patch.object(self.traces, 'doc_files', return_value=[path]):
            self.assertEqual(self.traces.scan_docs(), [])

    def test_clean_document_has_no_findings(self):
        self.assertEqual(self.scan_docs('本文描述当前状态。\n'), [])

    # -- code scope -------------------------------------------------------
    def scan_code(self, text: str) -> list[dict]:
        path = os.path.join(self.tmp.name, 'mod.py')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        with mock.patch.object(self.traces, 'code_files', return_value=[path]):
            return self.traces.scan_code()

    def test_code_comment_with_a_round_is_reported(self):
        findings = self.scan_code('# 第 2 轮补的\nx = 1\n')
        self.assertEqual(findings[0]['kind'], 'review-round')

    def test_migration_note_is_reported(self):
        findings = self.scan_code('# 迁移自旧模块\nx = 1\n')
        self.assertEqual(findings[0]['kind'], 'migration-note')

    def test_docstring_lines_are_scanned(self):
        findings = self.scan_code('"""以前是三条分支。"""\n')
        self.assertTrue(findings)

    def test_plain_code_is_clean(self):
        self.assertEqual(self.scan_code('x = 1\ny = 2\n'), [])

    # -- helpers and CLI --------------------------------------------------
    def test_comment_lines_marks_comments_and_docstrings(self):
        lines = self.traces.comment_lines('# c\nx = 1\n"""d"""\n')
        self.assertEqual([n for n, _ in lines], [1, 3])

    def test_json_output_reports_the_scope(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.traces.main(['--kind', 'docs', '--json'])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertEqual(payload['kind'], 'docs')

    def test_human_output_names_the_scope(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.traces.main(['--kind', 'code'])
        self.assertIn('代码', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
