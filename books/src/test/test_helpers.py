#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
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
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'sources'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

HAS_PYPDF = importlib.util.find_spec('pypdf') is not None


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path


class TestBalanceCheckHelpers(FixtureCase):
    def test_count_lines(self):
        bc = self.module('balance_check')
        self.assertEqual(bc.count_lines('a\nb\nc\n'), 3)

    def test_count_figures(self):
        bc = self.module('balance_check')
        text = '**图 1-1: 展示**\n**图 2-3: 对比**\n**图 A-1: 标注**\n'
        self.assertEqual(bc.count_figures(text), 3)

    def test_count_source_refs(self):
        bc = self.module('balance_check')
        self.assertEqual(bc.count_source_refs('见 MVStore.java:12 与 Page.java:7'), 2)

    def test_glossary_chapter_index(self):
        bc = self.module('balance_check')
        index = bc.load_glossary_chapter_index()
        self.assertIsInstance(index, dict)
        self.assertTrue(index, 'fixture glossary should contribute chapter hits')

    def test_index_chapter_index(self):
        bc = self.module('balance_check')
        index = bc.load_index_chapter_index()
        self.assertIsInstance(index, dict)

    def test_collect_metrics_and_render(self):
        bc = self.module('balance_check')
        metrics = bc.collect_metrics()
        self.assertIn('totals', metrics)
        self.assertGreaterEqual(metrics['totals']['files'], 1)
        rendered = bc.render_markdown(metrics)
        self.assertIn('| 文件 |', rendered)

    def test_render_diff(self):
        bc = self.module('balance_check')
        current = bc.collect_metrics()
        baseline = bc.collect_metrics()
        diff = bc.render_diff(current, baseline)
        self.assertIsInstance(diff, str)


class TestSmartAuditHelpers(FixtureCase):
    def test_count_diagrams_detects_blocks(self):
        smart = self.module('_audit_smart')
        text = '```text\n┌──┐\n│ab│\n└──┘\n```\n'
        self.assertEqual(smart.count_diagrams(text), 1)

    def test_count_diagrams_ignores_short_blocks(self):
        smart = self.module('_audit_smart')
        self.assertEqual(smart.count_diagrams('```text\nab\n```\n'), 0)

    def test_build_exempt_ranges_for_appendix_file(self):
        smart = self.module('_audit_smart')
        lines = ['# 附录 A 案例研究', '', '## 附：小节', '正文']
        headings = [(1, '附录 A 案例研究', 1), (2, '附：小节', 3)]
        ranges = smart.build_exempt_ranges(headings, lines)
        self.assertIsInstance(ranges, list)

    def test_check_figure_refs_runs(self):
        smart = self.module('_audit_smart')
        smart.check_figure_refs()  # prints a report; must not raise


class TestFigureClusterHelpers(FixtureCase):
    FIGURES = (
        '展示三个组件之间的调用关系与数据流向。\n\n'
        '**图 1-1: 展示组件 A 的调用**\n\n'
        '**图 1-2: 展示组件 B 的调用**\n\n'
        '**图 1-3: 展示组件 C 的调用**\n'
    )

    def test_find_clusters_with_bridge(self):
        clusters = self.module('_audit_figure_clusters')
        path = self.write('data/manuscript/cluster.md', self.FIGURES)
        found = clusters.find_clusters(path, min_figs=3, window=40)
        self.assertEqual(len(found), 1)

    def test_find_clusters_without_bridge(self):
        clusters = self.module('_audit_figure_clusters')
        path = self.write('data/manuscript/cluster2.md',
                          '**图 2-1: 展示 A**\n\n**图 2-2: 展示 B**\n\n**图 2-3: 展示 C**\n')
        found = clusters.find_clusters(path, min_figs=3, window=40)
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]['bridged'])

    def test_no_cluster_below_threshold(self):
        clusters = self.module('_audit_figure_clusters')
        path = self.write('data/manuscript/single.md', '**图 3-1: 展示 A**\n')
        self.assertEqual(clusters.find_clusters(path, min_figs=3, window=40), [])


class TestGlossaryBuilder(FixtureCase):
    def test_parse_glossary_v6(self):
        builder = self.module('build_glossary')
        entries = builder.parse_glossary_v6()
        self.assertIn('ACID', entries)
        self.assertEqual(entries['ACID']['chapters'], [1])
        self.assertTrue(entries['ACID']['section_refs'])

    def test_parse_glossary_skips_malformed_lines(self):
        builder = self.module('build_glossary')
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- 无加粗术语\n- **Term**: 释义\n  **章节**：第2章 §2.1\n')
        entries = builder.parse_glossary_v6()
        self.assertEqual(list(entries), ['Term'])


class TestSourceFreshnessHelpers(FixtureCase):
    def test_resolve_and_verify(self):
        sfc = self.module('source_freshness_check')
        with tempfile.TemporaryDirectory() as tmp:
            java = os.path.join(tmp, 'MVStore.java')
            with open(java, 'w', encoding='utf-8') as fh:
                fh.write('class MVStore {\n  void open() {}\n}\n')
            index = {'MVStore': [java]}
            ref = sfc.Reference('ch1.md', 3, 'MVStore', 2)
            resolved = sfc.resolve_references([ref], index)
            self.assertEqual(resolved[0].status, 'FOUND')
            checks = sfc.verify_line_numbers(resolved)
            self.assertEqual(checks[0].status, 'OK')

    def test_verify_line_numbers_flags_offset(self):
        sfc = self.module('source_freshness_check')
        with tempfile.TemporaryDirectory() as tmp:
            java = os.path.join(tmp, 'A.java')
            with open(java, 'w', encoding='utf-8') as fh:
                fh.write('class A {}\n')
            index = {'A': [java]}
            resolved = sfc.resolve_references([sfc.Reference('ch.md', 1, 'A', 99)], index)
            checks = sfc.verify_line_numbers(resolved)
            self.assertEqual(checks[0].status, 'OFFSET')

    def test_missing_class_reported(self):
        sfc = self.module('source_freshness_check')
        resolved = sfc.resolve_references(
            [sfc.Reference('ch.md', 1, 'NoSuchClass', 1)], {})
        self.assertEqual(resolved[0].status, 'MISSING')

    def test_ambiguous_class_reported(self):
        sfc = self.module('source_freshness_check')
        resolved = sfc.resolve_references(
            [sfc.Reference('ch.md', 1, 'Dup', 1)], {'Dup': ['a.java', 'b.java']})
        self.assertEqual(resolved[0].status, 'AMBIGUOUS')

    def test_claim_key_is_stable(self):
        sfc = self.module('source_freshness_check')
        a = sfc._claim_key('ch1.md', 'MVMap', 'open')
        b = sfc._claim_key('ch1.md', 'MVMap', 'open')
        self.assertEqual(a, b)
        self.assertNotEqual(a, sfc._claim_key('ch2.md', 'MVMap', 'open'))


@unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
class TestVerifyPdfOnSyntheticFile(FixtureCase):
    """Exercise the PDF checker against a PDF we build ourselves."""

    def build_pdf(self) -> tuple[str, str]:
        from pypdf import PdfReader, PdfWriter

        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=595, height=842)
        writer.add_outline_item('第1章 测试章节', 0)
        writer.add_outline_item('1.1 小节', 1)

        pdf_path = os.path.join(self.root, 'dist', 'synthetic.pdf')
        with open(pdf_path, 'wb') as fh:
            writer.write(fh)

        # A TOC link annotation pointing at page 0, named toc-link-0.
        reader = PdfReader(pdf_path, strict=False)
        html = ('<h1 id="a">第1章 测试章节</h1><h2 id="b">1.1 小节</h2>'
                '<nav id="toc-page-nav"><a href="#a">第1章 测试章节</a>'
                '<a href="#b">1.1 小节</a></nav>')
        html_path = os.path.join(self.root, 'dist', 'synthetic.html')
        with open(html_path, 'w', encoding='utf-8') as fh:
            fh.write(html)
        del reader
        return pdf_path, html_path

    def test_outline_and_toc_checks_run(self):
        verify_pdf = self.module('verify_pdf')
        pdf_path, html_path = self.build_pdf()
        report = verify_pdf.verify(pdf_path, html_path)
        names = [name for name, _ok, _d in report.checks]
        self.assertIn('OUTLINE', names)
        self.assertIn('TOC_COUNT', names)
        self.assertIn('PAGES', names)
        outline_check = next(c for c in report.checks if c[0] == 'OUTLINE')
        self.assertTrue(outline_check[1], outline_check[2])

    def test_missing_html_reported(self):
        verify_pdf = self.module('verify_pdf')
        pdf_path, _ = self.build_pdf()
        report = verify_pdf.verify(pdf_path, os.path.join(self.root, 'nope.html'))
        self.assertIn('SOURCE_HTML', [n for n, _d in report.failures])


class TestVerifyEpubFailures(FixtureCase):
    def test_manifest_missing_entry(self):
        verify_epub = self.module('verify_epub')
        import zipfile
        path = os.path.join(self.root, 'dist', 'broken.epub')
        opf = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
               'version="3.0"><metadata/><manifest>'
               '<item id="x" href="missing.xhtml" media-type="application/xhtml+xml"/>'
               '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
               'properties="nav"/></manifest><spine><itemref idref="x"/></spine></package>')
        container = ('<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:'
                     'opendocument:xmlns:container" version="1.0"><rootfiles>'
                     '<rootfile full-path="EPUB/content.opf" media-type="application/'
                     'oebps-package+xml"/></rootfiles></container>')
        nav = ('<html xmlns="http://www.w3.org/1999/xhtml"><body><nav>'
               '<a href="missing.xhtml">x</a></nav></body></html>')
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('mimetype', 'application/epub+zip', zipfile.ZIP_STORED)
            zf.writestr('META-INF/container.xml', container)
            zf.writestr('EPUB/content.opf', opf)
            zf.writestr('EPUB/nav.xhtml', nav)
        report = verify_epub.verify(path)
        self.assertIn('MANIFEST', [n for n, _d in report.failures])


if __name__ == '__main__':
    unittest.main()
