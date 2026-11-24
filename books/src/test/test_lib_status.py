"""Status lines degrade instead of raising: a missing file must never break a report.

The web console and the TUI both print these, so a deleted artifact or a missing
optional reader has to produce an empty or placeholder string, not an exception.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

_status = __import__('lib.status', fromlist=['_mb', '_pages', '_pages_cached', '_stamp'])


class ArtifactLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.missing = os.path.join(self.tmp.name, 'gone.pdf')

    def test_a_missing_file_has_no_stamp(self):
        self.assertEqual(_status._stamp(self.missing), '')

    def test_a_present_file_has_a_minute_stamp(self):
        path = os.path.join(self.tmp.name, 'there.pdf')
        with open(path, 'wb') as handle:
            handle.write(b'%PDF')
        self.assertRegex(_status._stamp(path), r'^\d{4}-\d\d-\d\d \d\d:\d\d$')

    def test_a_missing_file_has_no_size(self):
        self.assertEqual(_status._mb(self.missing), '?')

    def test_a_present_file_reports_megabytes(self):
        path = os.path.join(self.tmp.name, 'there.pdf')
        with open(path, 'wb') as handle:
            handle.write(b'x' * 2048)
        self.assertEqual(_status._mb(path), '0.00 MB')

    def test_a_missing_file_has_no_page_count(self):
        self.assertEqual(_status._pages(self.missing), '')

    def test_a_page_count_skips_everything_that_is_not_a_pdf(self):
        self.assertEqual(_status._pages_cached('book.epub', 1.0), '')
        self.assertEqual(_status._pages_cached('book.html', 1.0), '')

    def test_a_missing_reader_is_not_an_error(self):
        with mock.patch.dict('sys.modules', {'pypdf': None}):
            self.assertEqual(_status._pages_cached('book.pdf', 1.0), '')

    def test_an_unreadable_pdf_has_no_page_count(self):
        reader = mock.Mock(side_effect=RuntimeError('broken'))
        module = mock.Mock(PdfReader=reader)
        with mock.patch.dict('sys.modules', {'pypdf': module}):
            self.assertEqual(_status._pages_cached('/tmp/broken.pdf', 2.0), '')

    def test_a_pdf_reports_its_page_count(self):
        reader = mock.Mock()
        reader.return_value.pages = [1, 2, 3]
        module = mock.Mock(PdfReader=reader)
        with mock.patch.dict('sys.modules', {'pypdf': module}):
            self.assertEqual(_status._pages_cached('/tmp/three.pdf', 3.0), '3 页')


if __name__ == '__main__':
    unittest.main()
