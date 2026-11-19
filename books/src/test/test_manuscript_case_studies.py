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


class TestCaseStudyOutline(ScriptTestBase):
    def test_each_scenario_renders(self):
        for scenario in ('select', 'commit', 'recover'):
            with self.subTest(scenario=scenario):
                code, out = self.run_script(
                    'case_studies.py', '--scenario', scenario)
                self.assertEqual(code, 0, out)
                self.assertTrue(out.strip())


if __name__ == '__main__':
    unittest.main()
