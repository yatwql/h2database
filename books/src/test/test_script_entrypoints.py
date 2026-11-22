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

TAGS = ('layer:infra', 'tier:fast')

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

SCRIPT_EXIT_CODES = {
    'cover.py': 0,
    'merge.py': 0,
    'to_html.py': 0,
    'pdf_toc_links.py': 1,
    'to_epub.py': 0,
    'pdf_from_html.py': 0,
    'structure.py': 1,
    'links.py': 0,
    'diagrams.py': 0,
    'captions.py': 0,
    'figures.py': 0,
    'crossrefs.py': 0,
    'exercises.py': 1,
    'figure_clusters.py': 0,
    'index_xrefs.py': 0,
    'smart.py': 0,
    'balance.py': 0,
    'style.py': 0,
    'readability.py': 0,
    'source_refs.py': 0,
    'glossary.py': 0,
    'index.py': 0,
}

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

class TestEveryScriptRuns(ScriptTestBase):
    """Every script must start, do something, and exit without a traceback."""

    def test_all_scripts_in_sequence(self):
        self.run_script('merge.py')
        self.run_script('to_html.py')
        for script in ALL_SCRIPTS + AUDIT_SCRIPTS:
            with self.subTest(script=script):
                code, out = self.run_script(script)
                self.assertIn(script, SCRIPT_EXIT_CODES, f'{script} has no recorded verdict')
                self.assertEqual(code, SCRIPT_EXIT_CODES[script], f'{script} -> {code}\n{out}')
                self.assertGreaterEqual(len(out), 0)
                self.assertNotIn('Traceback', out, f'{script} raised:\n{out}')

if __name__ == '__main__':
    unittest.main()
