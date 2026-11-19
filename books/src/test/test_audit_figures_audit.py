#!/usr/bin/env python3
"""Tests for the print/delivery gates: _audit_ascii, verify_epub, verify_pdf."""

import importlib
import os
import sys
import tempfile
import unittest

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

audit_ascii = importlib.import_module('diagrams')
verify_epub = importlib.import_module('verify_epub')
verify_pdf = importlib.import_module('verify_pdf')

class TestAuditFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, text: str) -> str:
        path = os.path.join(self.tmp.name, 'ch.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def kinds(self, text: str, max_cols: int = 20) -> list[str]:
        return [v[2] for v in audit_ascii.audit_file(self.write(text), max_cols)]

    def test_wide_line_detected(self):
        kinds = self.kinds('```text\n' + 'x' * 30 + '\n```\n')
        self.assertIn('WIDE_LINE', kinds)

    def test_cjk_width_uses_two_columns(self):
        # 12 CJK chars == 24 columns > 20
        kinds = self.kinds('```text\n' + '架' * 12 + '\n```\n', max_cols=20)
        self.assertIn('WIDE_LINE', kinds)

    def test_narrow_diagram_passes(self):
        kinds = self.kinds('```text\n+--+\n|ab|\n+--+\n```\n')
        self.assertEqual([k for k in kinds if k == 'WIDE_LINE'], [])

    def test_trailing_whitespace_detected(self):
        kinds = self.kinds('```text\nab   \n```\n')
        self.assertIn('TRAILING_WS', kinds)

    def test_tab_detected(self):
        kinds = self.kinds('```text\na\tb\n```\n')
        self.assertIn('TAB_CHAR', kinds)

    def test_mixed_box_detected(self):
        kinds = self.kinds('```text\n┌──┐\n+--+\n└──┘\n```\n')
        self.assertIn('MIXED_BOX', kinds)

if __name__ == '__main__':
    unittest.main()
