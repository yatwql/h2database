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
HAS_PYPDF = importlib.util.find_spec('pypdf') is not None
HAS_PLAYWRIGHT = importlib.util.find_spec('playwright') is not None
HAS_PANDOC = bool(__import__('shutil').which('pandoc'))


BUILD_SCRIPTS = ['cover.py', 'merge.py', 'to_html.py']

ALL_SCRIPTS = [
    'cover.py', 'merge.py', 'to_html.py',
    'pdf_toc_links.py', 'to_epub.py', 'pdf_from_html.py',
    'structure.py',
]

AUDIT_SCRIPTS = [
    'links.py',
    'diagrams.py',
    'captions.py',
    'figures.py',
    'crossrefs.py',
    'exercises.py',
    'figure_clusters.py',
    'index_xrefs.py',
    'smart.py',
    'balance.py',
    'style.py',
    'readability.py',
    'source_refs.py',
    'glossary.py',
    'index.py',
]


class ScriptTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_script(self, script: str, *args: str) -> tuple[int, str]:
        return _fixture.run_inproc(self.root, script, *args)

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def read(self, *parts: str) -> str:
        with open(self.path(*parts), encoding='utf-8') as fh:
            return fh.read()


class TestBuildScripts(ScriptTestBase):
    def test_cover_stats_runs(self):
        code, out = self.run_script('cover.py')
        self.assertEqual(code, 0, out)
        self.assertIn('cover.md', out)

    def test_rebuild_merged_writes_dist(self):
        code, out = self.run_script('merge.py')
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(self.path('dist', 'test-book.md')))

    def test_generate_html_runs_after_merge(self):
        self.run_script('merge.py')
        code, out = self.run_script('to_html.py')
        self.assertEqual(code, 0, out)
        html = self.read('dist', 'test-book.html')
        self.assertIn('<h1 id="第1章-测试章节">', html)
        self.assertIn('id="toc-page-nav"', html)


class TestAuditScripts(ScriptTestBase):
    def test_every_audit_runs_without_crashing(self):
        for script in AUDIT_SCRIPTS:
            with self.subTest(script=script):
                code, out = self.run_script(script)
                self.assertIn(code, (0, 1), f'{script} crashed:\n{out}')
                self.assertNotIn('Traceback', out, f'{script} raised:\n{out}')

    def test_link_audit_detects_break(self):
        with open(self.path('data', 'manuscript', 'ch1-test.md'), 'a', encoding='utf-8') as fh:
            fh.write('\n[坏链接](missing.md)\n')
        code, out = self.run_script('links.py')
        self.assertEqual(code, 1, out)
        self.assertIn('BROKEN_FILE', out)

    def test_ascii_audit_detects_wide_diagram(self):
        with open(self.path('data', 'manuscript', 'ch1-test.md'), 'a', encoding='utf-8') as fh:
            fh.write('\n```text\n' + 'x' * 130 + '\n```\n')
        code, out = self.run_script('diagrams.py')
        self.assertEqual(code, 1, out)
        self.assertIn('WIDE_LINE', out)

    def test_caption_audit_strict_flags_bare_noun(self):
        with open(self.path('data', 'manuscript', 'ch1-test.md'), 'a', encoding='utf-8') as fh:
            fh.write('\n**图 1-9: MVStore 架构**\n')
        code, out = self.run_script('captions.py', '--threshold', 'strict')
        self.assertEqual(code, 1, out)
        self.assertIn('NO_VERB', out)

    def test_glossary_builder_handles_fixture(self):
        code, out = self.run_script('glossary.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)

    def test_index_builder_handles_fixture(self):
        code, out = self.run_script('index.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)

    def test_glossary_builder_check_mode(self):
        code, out = self.run_script('glossary.py', '--check')
        self.assertIn(code, (0, 1), out)

    def test_index_builder_hierarchy_check(self):
        code, out = self.run_script('index.py', '--hierarchy-check')
        self.assertIn(code, (0, 1), out)

    def test_source_freshness_handles_missing_source_tree(self):
        code, out = self.run_script('source_refs.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)


class TestEveryScriptRuns(ScriptTestBase):
    """Every script must start, do something, and exit without a traceback."""

    def test_all_scripts_in_sequence(self):
        self.run_script('merge.py')
        self.run_script('to_html.py')
        for script in ALL_SCRIPTS + AUDIT_SCRIPTS:
            with self.subTest(script=script):
                code, out = self.run_script(script)
                # 2 = the environment lacks an optional tool (chromium/pandoc)
                self.assertIn(code, (0, 1, 2), f'{script} -> {code}\n{out}')
                self.assertNotIn('Traceback', out, f'{script} raised:\n{out}')


class TestCaseStudyOutline(ScriptTestBase):
    def test_each_scenario_renders(self):
        for scenario in ('select', 'commit', 'recover'):
            with self.subTest(scenario=scenario):
                code, out = self.run_script(
                    'case_studies.py', '--scenario', scenario)
                self.assertEqual(code, 0, out)
                self.assertTrue(out.strip())


class TestAnnotateTermsModes(ScriptTestBase):
    def test_default_mode_annotates_chapters(self):
        code, out = self.run_script('terms.py')
        self.assertEqual(code, 0, out)
        self.assertIn('Updated', out)

    def test_check_related_mode(self):
        code, out = self.run_script('terms.py', '--check-related')
        self.assertIn(code, (0, 1), out)

    def test_report_missing_mode(self):
        code, out = self.run_script('terms.py', '--report-missing')
        self.assertEqual(code, 0, out)

    def test_check_mode(self):
        code, out = self.run_script('terms.py', '--check')
        self.assertIn(code, (0, 1), out)


class TestPdfToolchain(ScriptTestBase):
    """Chromium-backed pipeline: PDF render -> verify -> TOC links -> print PDF."""

    def setUp(self):
        super().setUp()
        self.run_script('merge.py')
        self.run_script('to_html.py')

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_generate_pdf_then_verify(self):
        code, out = self.run_script('to_pdf.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)
        if code == 0:
            code2, out2 = self.run_script('verify_pdf.py')
            self.assertIn(code2, (0, 1), out2)
            self.assertNotIn('Traceback', out2)

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_add_pdf_toc_links_runs(self):
        self.run_script('to_pdf.py')
        code, out = self.run_script('pdf_toc_links.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_pdf_print_grade_runs(self):
        code, out = self.run_script('print_pdf.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)


class TestFullDeliveryPipeline(ScriptTestBase):
    """Build -> PDF (+TOC links) -> print PDF -> EPUB -> verify, all in-process."""

    def setUp(self):
        super().setUp()
        self.run_script('merge.py')
        self.run_script('to_html.py')

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_pdf_render_verify_and_toc_links(self):
        code, out = self.run_script('to_pdf.py')
        self.assertEqual(code, 0, out[-400:])
        code, out = self.run_script('verify_pdf.py')
        self.assertIn(code, (0, 1), out[-400:])
        code, out = self.run_script('pdf_toc_links.py')
        self.assertIn(code, (0, 1), out[-400:])
        code, out = self.run_script('verify_pdf.py', '--require-toc-links')
        self.assertIn(code, (0, 1), out[-400:])

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_print_grade_pdf(self):
        self.run_script('to_pdf.py')
        code, out = self.run_script('print_pdf.py')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertNotIn('Traceback', out)

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_pdf_from_html(self):
        code, out = self.run_script('pdf_from_html.py')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertNotIn('Traceback', out)

    @unittest.skipUnless(SLOW and HAS_PANDOC, 'slow suite: set BOOK_SLOW=1')
    def test_epub_build_and_verify(self):
        code, out = self.run_script('to_epub.py')
        self.assertEqual(code, 0, out[-400:])
        code, out = self.run_script('verify_epub.py')
        self.assertEqual(code, 0, out[-400:])


class TestDeliveryScripts(ScriptTestBase):
    def setUp(self):
        super().setUp()
        self.run_script('merge.py')
        self.run_script('to_html.py')

    @unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
    def test_verify_pdf_reports_missing_artifact(self):
        code, out = self.run_script('verify_pdf.py')
        self.assertEqual(code, 1)
        self.assertIn('EXISTS', out)

    @unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
    def test_verify_epub_reports_missing_artifact(self):
        code, out = self.run_script('verify_epub.py')
        self.assertEqual(code, 1)
        self.assertIn('EXISTS', out)

    @unittest.skipUnless(SLOW and HAS_PANDOC, 'slow suite: set BOOK_SLOW=1')
    def test_generate_epub_smoke(self):
        code, out = self.run_script('to_epub.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_pdf_from_html_smoke(self):
        code, out = self.run_script('pdf_from_html.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)


class TestMakeEntryPoint(ScriptTestBase):
    def test_make_doctor(self):
        code, out = _fixture.run_inproc(self.root, 'make.py', 'doctor')
        self.assertIn(code, (0, 1), out)
        self.assertIn('python', out)

    def test_make_build_only(self):
        code, out = _fixture.run_inproc(
            self.root, 'make.py', 'build', '--only', 'cover_stats')
        self.assertEqual(code, 0, out)


if __name__ == '__main__':
    unittest.main()
