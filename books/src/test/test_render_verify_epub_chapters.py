"""A chapter file must carry exactly one h1 — that is what made it a file."""
from __future__ import annotations

import io
import unittest
import zipfile

import _fixture

TAGS = ('layer:render', 'tier:fast')

_fixture.ensure_tools_path()

_verify = __import__('render.verify_epub', fromlist=['Report', '_check_chapters'])
Report = _verify.Report
_check_chapters = _verify._check_chapters


def archive_with(bodies: dict[str, str]) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as handle:
        for name, html in bodies.items():
            handle.writestr(name, html)
    return zipfile.ZipFile(buffer)


class ChapterCheckTest(unittest.TestCase):
    def _run(self, bodies):
        report = Report()
        with archive_with(bodies) as archive:
            _check_chapters(report, archive, archive.namelist())
        return report.checks[-1]

    def test_one_heading_per_file_passes(self):
        name, ok, detail = self._run({'EPUB/text/ch001.xhtml': '<h1>一</h1>',
                                      'EPUB/text/ch002.xhtml': '<h1>二</h1>'})
        self.assertTrue(ok, detail)
        self.assertIn('2 chapter files', detail)

    def test_a_file_with_two_headings_fails(self):
        _, ok, detail = self._run({'EPUB/text/ch001.xhtml': '<h1>一</h1><h1>二</h1>'})
        self.assertFalse(ok)
        self.assertIn('ch001.xhtml has 2', detail)

    def test_a_file_without_a_heading_fails(self):
        _, ok, detail = self._run({'EPUB/text/ch001.xhtml': '<p>无标题</p>'})
        self.assertFalse(ok)
        self.assertIn('has 0', detail)

    def test_no_body_files_fails(self):
        _, ok, detail = self._run({'EPUB/nav.xhtml': '<h1>导航</h1>'})
        self.assertFalse(ok)
        self.assertIn('no chapter files', detail)


if __name__ == '__main__':
    unittest.main()
