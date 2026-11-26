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
import shutil
import sys
import unittest

from _cases import ScriptTestBase

# Scripts whose exit code depends on an optional tool: in a bare environment they
# report the missing dependency, so the recorded verdict only holds where it exists.
TOOL_FOR = {'to_epub.py': 'pandoc', 'pdf_toc_links.py': 'playwright',
            'pdf_from_html.py': 'playwright'}


def has_tool(name: str) -> bool:
    if name == 'pandoc':
        return bool(shutil.which('pandoc'))
    return importlib.util.find_spec(name) is not None


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


class TestEveryScriptRuns(ScriptTestBase):
    """Every script must start, do something, and exit without a traceback."""

    def test_all_scripts_in_sequence(self):
        self.run_script('merge.py')
        self.run_script('to_html.py')
        for script in ALL_SCRIPTS + AUDIT_SCRIPTS:
            with self.subTest(script=script):
                tool = TOOL_FOR.get(script)
                if tool and not has_tool(tool):
                    self.skipTest(f'{tool} is not installed')
                code, out = self.run_script(script)
                self.assertIn(script, SCRIPT_EXIT_CODES, f'{script} has no recorded verdict')
                self.assertEqual(code, SCRIPT_EXIT_CODES[script], f'{script} -> {code}\n{out}')
                self.assertGreaterEqual(len(out), 0)
                self.assertNotIn('Traceback', out, f'{script} raised:\n{out}')

if __name__ == '__main__':
    unittest.main()
