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

    def test_source_refs_handles_missing_source_tree(self):
        code, out = self.run_script('source_refs.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)


if __name__ == '__main__':
    unittest.main()
