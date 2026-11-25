#!/usr/bin/env python3
"""In-process smoke + behaviour tests for every delivery script.

Each script is executed with ``runpy`` against the fixture book, so coverage
counts the real code paths (a subprocess run would not) while staying
deterministic and offline.

Environment-dependent scripts (PDF/EPUB toolchain) run only when their
optional dependencies are importable; otherwise they are skipped by name so the
gap stays visible instead of silently passing.
"""

import importlib.util
import os
import sys
import unittest

from _cases import ScriptTestBase

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

SLOW = os.environ.get('BOOK_SLOW') == '1'
HAS_PLAYWRIGHT = importlib.util.find_spec('playwright') is not None


class TestPdfToolchain(ScriptTestBase):
    """Chromium-backed pipeline: PDF render -> verify -> TOC links -> print PDF."""

    def setUp(self):
        super().setUp()
        self.run_script('merge.py')
        self.run_script('to_html.py')

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_to_pdf_then_verify(self):
        code, out = self.run_script('to_pdf.py')
        self.assertEqual(code, 0, out[-400:])
        self.assertNotIn('Traceback', out)
        code2, out2 = self.run_script('verify_pdf.py')
        self.assertEqual(code2, 0, out2[-400:])
        self.assertIn('PDF 交付校验通过', out2)
        self.assertNotIn('Traceback', out2)

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_add_pdf_toc_links_runs(self):
        self.run_script('to_pdf.py')
        code, out = self.run_script('pdf_toc_links.py')
        self.assertEqual(code, 0, out[-400:])
        self.assertIn('TOC links added', out)
        self.assertNotIn('Traceback', out)

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_pdf_print_grade_runs(self):
        code, out = self.run_script('print_pdf.py')
        self.assertEqual(code, 0, out[-400:])
        self.assertIn('Print-grade PDF', out)
        self.assertNotIn('Traceback', out)

if __name__ == '__main__':
    unittest.main()
