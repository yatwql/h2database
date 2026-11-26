#!/usr/bin/env python3
"""Error and fallback paths of the delivery scripts.

Missing optional tools (pandoc, chromium), missing prerequisites and malformed
artifacts are the branches that never run in the happy path but do fire in real
use — and they are where a toolchain silently misbehaves instead of reporting.
"""

import os
import sys
import unittest

from _cases import Base

TAGS = ('layer:render', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestDeliveryPrerequisites(Base):
    def test_epub_without_pandoc_exits_cleanly(self):
        code, out = self.run_script('to_epub.py', env={'PATH': '/nonexistent'})
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('pandoc', out.lower())

    def test_pdf_without_html_exits_cleanly(self):
        code, out = self.run_script('pdf_from_html.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('cannot read', out)

    def test_print_grade_builds_from_the_html(self):
        self.run_script('merge.py')
        self.run_script('to_html.py')
        code, out = self.run_script('print_pdf.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('Print-grade PDF', out)

    def test_toc_links_without_pdf(self):
        self.run_script('merge.py')
        self.run_script('to_html.py')
        code, out = self.run_script('pdf_toc_links.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('PDF', out)

if __name__ == '__main__':
    unittest.main()
