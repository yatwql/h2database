#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

from _cases import FixtureCase

TAGS = ('layer:audit', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestSmartAuditHelpers(FixtureCase):
    def test_count_diagrams_detects_blocks(self):
        smart = self.module('smart')
        text = '```text\n┌──┐\n│ab│\n└──┘\n```\n'
        self.assertEqual(smart.count_diagrams(text), 1)

    def test_count_diagrams_ignores_short_blocks(self):
        smart = self.module('smart')
        self.assertEqual(smart.count_diagrams('```text\nab\n```\n'), 0)

    def test_check_figure_refs_reports_the_coverage_verdict(self):
        smart = self.module("smart")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            smart.check_figure_refs()
        text = buffer.getvalue()
        self.assertIn("TOTAL:", text)
        self.assertIn("COVERAGE:", text)

if __name__ == '__main__':
    unittest.main()
