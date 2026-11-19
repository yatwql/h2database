#!/usr/bin/env python3
"""Tests for the print/delivery gates: _audit_ascii, verify_epub, verify_pdf."""
import importlib
import os
import sys
import tempfile
import unittest
import zipfile
from typing import ClassVar

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'sources'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

audit_ascii = importlib.import_module('_audit_ascii')
verify_epub = importlib.import_module('verify_epub')
verify_pdf = importlib.import_module('verify_pdf')


class TestDisplayWidth(unittest.TestCase):
    def test_ascii_is_one_column(self):
        self.assertEqual(audit_ascii.display_width('abc'), 3)

    def test_cjk_counts_two_columns(self):
        self.assertEqual(audit_ascii.display_width('架构'), 4)

    def test_mixed(self):
        self.assertEqual(audit_ascii.display_width('MV 存储'), 7)


class TestTextBlocks(unittest.TestCase):
    LINES: ClassVar[list[str]] = [
        '正文',
        '```text',
        '┌──────┐',
        '│ 架构 │',
        '└──────┘',
        '```',
        '```java',
        'class A {}',
        '```',
    ]

    def test_only_text_blocks_collected(self):
        blocks = audit_ascii.text_blocks(self.LINES)
        self.assertEqual(len(blocks), 1)
        start, block = blocks[0]
        self.assertEqual(start, 3)
        self.assertEqual(block[0], '┌──────┐')

    def test_java_block_ignored(self):
        blocks = audit_ascii.text_blocks(self.LINES)
        self.assertNotIn('class A {}', [line for _s, b in blocks for line in b])


class TestMixedBorders(unittest.TestCase):
    def test_mixed_reported(self):
        block = ['┌────┐', '+----+', '│ 组件 │']
        self.assertTrue(audit_ascii._mixes_borders(block))

    def test_box_only_is_fine(self):
        block = ['┌────┐', '│ 组件 │', '└────┘']
        self.assertFalse(audit_ascii._mixes_borders(block))

    def test_ascii_only_is_fine(self):
        block = ['+----+', '| ab |', '+----+']
        self.assertFalse(audit_ascii._mixes_borders(block))


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


class TestEpubVerification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def build_epub(self, *, omit_nav: bool = False, bad_mimetype: bool = False) -> str:
        path = os.path.join(self.tmp.name, 'book.epub')
        nav = ('<?xml version="1.0" encoding="utf-8"?>'
               '<html xmlns="http://www.w3.org/1999/xhtml"><body><nav>'
               '<a href="ch1.xhtml">第一章</a></nav></body></html>')
        opf = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata/>'
            '<manifest>'
            '<item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
            'properties="nav"/>'
            '</manifest>'
            '<spine><itemref idref="ch1"/></spine>'
            '</package>'
        )
        container = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
            'version="1.0"><rootfiles>'
            '<rootfile full-path="EPUB/content.opf" '
            'media-type="application/oebps-package+xml"/>'
            '</rootfiles></container>'
        )
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('mimetype', 'text/plain' if bad_mimetype
                        else 'application/epub+zip', zipfile.ZIP_STORED)
            zf.writestr('META-INF/container.xml', container)
            zf.writestr('EPUB/content.opf', opf)
            zf.writestr('EPUB/ch1.xhtml', '<html><body>正文</body></html>')
            if not omit_nav:
                zf.writestr('EPUB/nav.xhtml', nav)
        return path

    def test_valid_epub_passes(self):
        report = verify_epub.verify(self.build_epub())
        self.assertEqual(report.failures, [], report.checks)

    def test_bad_mimetype_fails(self):
        report = verify_epub.verify(self.build_epub(bad_mimetype=True))
        self.assertIn('MIMETYPE', [name for name, _d in report.failures])

    def test_missing_nav_file_fails(self):
        report = verify_epub.verify(self.build_epub(omit_nav=True))
        self.assertIn('MANIFEST', [name for name, _d in report.failures])

    def test_missing_epub_reports_exists(self):
        report = verify_epub.verify(os.path.join(self.tmp.name, 'nope.epub'))
        self.assertIn('EXISTS', [name for name, _d in report.failures])


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
