"""The PDF invariants judge a build without a reference edition."""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

_inv = __import__('audit.pdf_invariants', fromlist=['check', 'main'])
check = _inv.check
main = _inv.main


class CheckTest(unittest.TestCase):
    def test_a_missing_pdf_is_refused(self):
        self.assertEqual(main([os.path.join(tempfile.gettempdir(), 'nope.pdf')]), 2)

    def test_findings_are_returned_as_data(self):
        from pypdf import PdfWriter

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'one.pdf')
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            with open(path, 'wb') as handle:
                writer.write(handle)
            merged = os.path.join(directory, 'merged.md')
            with open(merged, 'w', encoding='utf-8') as handle:
                handle.write('# 一\n\n## 二\n')
            report = check(path, merged)
        self.assertEqual(report['pages'], 1)
        self.assertEqual(report['outline'], 0)
        self.assertEqual(report['headings'], 2)
        self.assertTrue(any('大纲' in p for p in report['problems']))

    def test_without_a_merged_file_the_outline_is_not_judged(self):
        from pypdf import PdfWriter

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'one.pdf')
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            with open(path, 'wb') as handle:
                writer.write(handle)
            report = check(path, None)
        self.assertIsNone(report['headings'])
        self.assertFalse(any('大纲' in p for p in report['problems']))


if __name__ == '__main__':
    unittest.main()
