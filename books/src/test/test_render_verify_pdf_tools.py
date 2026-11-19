#!/usr/bin/env python3
"""Tests for the print/delivery gates: _audit_ascii, verify_epub, verify_pdf."""

import importlib
import os
import sys
import tempfile
import unittest

TAGS = ('layer:render', 'tier:slow')

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

class TestPdfHelpers(unittest.TestCase):
    def test_html_headings_extracts_level_and_text(self):
        html = '<h1 id="a">第一章</h1><h2 id="b">1.1 <em>小节</em></h2>'
        self.assertEqual(verify_pdf.html_headings(html),
                         [(1, '第一章'), (2, '1.1 小节')])

    def test_html_headings_ignores_unidentified(self):
        self.assertEqual(verify_pdf.html_headings('<h1>无 id</h1>'), [])

    def test_missing_pdf_reports_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = verify_pdf.verify(os.path.join(tmp, 'x.pdf'),
                                       os.path.join(tmp, 'x.html'))
        self.assertIn('EXISTS', [name for name, _d in report.failures])

    def test_annotation_rect_guard(self):
        class Bare:
            pass

        self.assertEqual(verify_pdf._annotation_rect(Bare()), [])
        self.assertEqual(verify_pdf._annotation_rect({'/Rect': [1, 2, 3, 4]}),
                         [1.0, 2.0, 3.0, 4.0])

if __name__ == '__main__':
    unittest.main()
