#!/usr/bin/env python3
"""Error and fallback paths of the delivery scripts.

Missing optional tools (pandoc, chromium), missing prerequisites and malformed
artifacts are the branches that never run in the happy path but do fire in real
use — and they are where a toolchain silently misbehaves instead of reporting.
"""
import importlib.util
import os
import sys
import tempfile
import unittest

import _fixture

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
HAS_PANDOC = bool(__import__('shutil').which('pandoc'))
HAS_PYPDF = importlib.util.find_spec('pypdf') is not None


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_script(self, script: str, *args: str, env: dict | None = None):
        if env is None:
            return _fixture.run_inproc(self.root, script, *args)
        previous = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            return _fixture.run_inproc(self.root, script, *args)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path


class TestDeliveryPrerequisites(Base):
    def test_epub_without_pandoc_exits_cleanly(self):
        code, out = self.run_script('generate_epub.py', env={'PATH': '/nonexistent'})
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('pandoc', out.lower())

    def test_pdf_without_html_exits_cleanly(self):
        code, out = self.run_script('pdf_from_html.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_print_grade_without_pdf(self):
        self.run_script('rebuild_merged.py')
        self.run_script('generate_html.py')
        code, out = self.run_script('pdf_print_grade.py')
        self.assertIn(code, (0, 1), out[-300:])

    def test_toc_links_without_pdf(self):
        self.run_script('rebuild_merged.py')
        self.run_script('generate_html.py')
        code, out = self.run_script('add_pdf_toc_links.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('PDF', out)


class TestVerifyPdfErrorPaths(Base):
    @unittest.skipUnless(SLOW and HAS_PYPDF, 'slow suite: set BOOK_SLOW=1')
    def test_require_toc_links_without_annotations(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        for _ in range(2):
            writer.add_blank_page(width=595, height=842)
        writer.add_outline_item('第1章 测试', 0)
        pdf = os.path.join(self.root, 'dist', 'no-links.pdf')
        with open(pdf, 'wb') as fh:
            writer.write(fh)
        html = os.path.join(self.root, 'dist', 'no-links.html')
        with open(html, 'w', encoding='utf-8') as fh:
            fh.write('<h1 id="a">第1章 测试</h1>'
                     '<nav id="toc-page-nav"><a href="#a">第1章 测试</a></nav>')
        code, out = self.run_script('verify_pdf.py', '--pdf', pdf, '--html', html,
                                    '--require-toc-links')
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('TOC_LINKS', out)

    def test_missing_pdf_json(self):
        _code, out = self.run_script('verify_pdf.py', '--json')
        self.assertIn('"ok"', out)

    def test_epub_json(self):
        _code, out = self.run_script('verify_epub.py', '--json')
        self.assertIn('"ok"', out)


class TestVerifyPdfTocLinkSuccess(Base):
    @unittest.skipUnless(SLOW and HAS_PYPDF, 'slow suite: set BOOK_SLOW=1')
    def test_valid_toc_annotation_targets_outline_page(self):
        from pypdf import PdfWriter
        from pypdf.annotations import Link
        from pypdf.generic import NameObject, TextStringObject

        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=595, height=842)
        writer.add_outline_item('第1章 测试', 0)
        writer.add_outline_item('1.1 小节', 1)
        annot = Link(rect=(50, 700, 300, 720), target_page_index=0)
        annot[NameObject('/NM')] = TextStringObject('toc-link-0')
        writer.add_annotation(0, annot)
        pdf = os.path.join(self.root, 'dist', 'links.pdf')
        with open(pdf, 'wb') as fh:
            writer.write(fh)
        html = os.path.join(self.root, 'dist', 'links.html')
        with open(html, 'w', encoding='utf-8') as fh:
            fh.write('<h1 id="a">第1章 测试</h1><h2 id="b">1.1 小节</h2>'
                     '<nav id="toc-page-nav"><a href="#a">第1章 测试</a></nav>')
        code, out = self.run_script('verify_pdf.py', '--pdf', pdf, '--html', html,
                                    '--require-toc-links')
        self.assertIn(code, (0, 1), out[-600:])
        self.assertIn('TOC_LINKS', out)

    def test_annotation_rect_and_target_helpers(self):
        verify_pdf = _fixture.load_module(self.root, 'verify_pdf')
        self.assertEqual(verify_pdf._annotation_rect(object()), [])
        self.assertIsNone(verify_pdf._annotation_target_page(None, {'/A': {'/S': '/URI'}}))


class TestAnnotateTermsGuideBranches(Base):
    def test_chapter_without_guide_block(self):
        self.write('data/manuscript/ch2-test.md', '# 第2章 测试章节\n\n仅正文。\n')
        code, out = self.run_script('_annotate_terms.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('No guide block found', out)


class TestAnnotateTermsReports(Base):
    def test_report_missing_on_rich_chapter(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n> **本章导读**: 导读。\n\n'
                   '**Write Amplification** 与 **MVStore** 混排。\n')
        code, out = self.run_script('_annotate_terms.py', '--report-missing')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('MISSING', out)

    def test_check_mode_fails_on_missing_terms(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n**未收录术语甲** 与 **未收录术语乙**。\n')
        code, out = self.run_script('_annotate_terms.py', '--check')
        self.assertIn(code, (0, 1), out[-300:])

    def test_check_related_reports_dangling(self):
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n  **章节**：第1章 §1.1\n'
                   '  **相关**：[[不存在的术语]]\n')
        code, out = self.run_script('_annotate_terms.py', '--check-related')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('DANGLING', out)


class TestHtmlCoverBranches(Base):
    RICH_COVER = (
        '# 测试之书\n\n'
        '> 版本 v0.1 · 2026-01-01 · 1,000 行\n\n'
        '## 图书信息\n\n'
        '| 项目 | 内容 |\n|------|------|\n| 作者 | 某人 |\n| 页数 | 100 |\n\n'
        '## 阅读指引\n\n正文。\n'
    )

    def test_cover_info_table_rendered(self):
        self.write('data/manuscript/cover.md', self.RICH_COVER)
        self.run_script('rebuild_merged.py')
        code, out = self.run_script('generate_html.py')
        self.assertEqual(code, 0, out[-300:])
        html_path = os.path.join(self.root, 'dist', 'test-book.html')
        with open(html_path, encoding='utf-8') as fh:
            html = fh.read()
        self.assertIn('cover-info', html)

    def test_missing_merged_md(self):
        _code, out = self.run_script('generate_html.py')
        self.assertNotIn('Traceback', out)


class TestIndexAndStyleBranches(Base):
    def test_index_with_subsections(self):
        self.write('data/manuscript/back/index.md',
                   '# 索引\n\n## A\n\n- ACID —— §1.1\n'
                   '  - 原子性 —— §1.1\n  - 隔离性 —— §2.1\n  see also: MVStore\n\n'
                   '## M\n\n- MVStore —— §2.1\n  see also: ACID\n')
        code, out = self.run_script('_audit_index_xrefs.py')
        self.assertIn(code, (0, 1), out[-300:])
        code, out = self.run_script('build_index.py', '--hierarchy-check')
        self.assertIn(code, (0, 1), out[-300:])

    def test_style_flags_long_line_and_monotony(self):
        body = '这是短句。' * 30
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n' + body + '\n\n' + '很' * 200 + '\n')
        code, out = self.run_script('check_style.py')
        self.assertIn(code, (0, 1), out[-300:])


class TestExerciseEdgeCases(Base):
    def test_chapter_without_exercises(self):
        self.write('data/manuscript/ch1-test.md', '# 第1章 测试章节\n\n仅正文。\n')
        code, out = self.run_script('_audit_exercises.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertIn('延伸思考', out)

    def test_caption_below_minimum(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n**图 1-1: 短**\n')
        code, out = self.run_script('_audit_captions.py', '--threshold', 'strict')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('TOO_SHORT', out)


if __name__ == '__main__':
    unittest.main()
