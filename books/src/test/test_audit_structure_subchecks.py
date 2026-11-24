#!/usr/bin/env python3
"""structure.py: the branches a healthy build never takes.

The gate aggregates many sub-checks; each one is wrapped so a broken tool is
reported instead of aborting the run. Those wrappers are what these cases drive.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class StructureBranchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def gate(self, script: str = 'structure.py', *args: str):
        return _fixture.run_inproc(self.root, script, *args)

    def test_a_sub_check_that_cannot_run_is_reported_not_raised(self):
        import subprocess

        real_run = subprocess.run

        def failing(command, **kwargs):
            if any('index' in str(part) for part in command):
                raise OSError('tool exploded')
            return real_run(command, **kwargs)

        with mock.patch.object(subprocess, 'run', side_effect=failing):
            code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('Index', out)
        self.assertNotIn('Traceback', out)

    def test_a_missing_index_is_a_hard_failure(self):
        os.unlink(os.path.join(self.root, 'data', 'manuscript', 'back', 'index.md'))
        code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('Index', out)

    def test_a_broken_css_reference_warns_but_does_not_crash(self):
        code, out = self.gate()
        # the fixture book has its own gaps, so the gate exits 1; what matters
        # here is that the CSS check reported instead of raising
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('CSS', out)
        self.assertNotIn('Traceback', out)

    def test_the_gate_reports_each_failing_check_by_name(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n```text\nunclosed fence\n')
        code, out = self.gate()
        self.assertEqual(code, 1, out[-600:])
        self.assertIn('FAIL:', out)


if __name__ == '__main__':
    unittest.main()


class ExtractedChecksTest(unittest.TestCase):
    """The CSS-hook and builder-script checks, judged without running the script."""

    def setUp(self):
        self.structure = __import__('audit.structure', fromlist=['css_style_missing'])

    def test_every_hook_present_reports_nothing(self):
        source = '\n'.join(self.structure.CSS_HINTS.values())
        self.assertEqual(self.structure.css_style_missing(source), [])

    def test_a_missing_hook_is_named_with_its_selector(self):
        missing = self.structure.css_style_missing('h1::before')
        self.assertTrue(missing)
        self.assertIn('print styles (@media print)', missing)

    def test_a_broken_builder_script_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'glossary.py')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('def broken(:\n')
            broken, missing = self.structure.builder_script_problems({'glossary.py': path})
        self.assertEqual(missing, [])
        self.assertIn('syntax error', broken[0])

    def test_a_missing_builder_script_is_only_a_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            broken, missing = self.structure.builder_script_problems(
                {'glossary.py': os.path.join(directory, 'gone.py')})
        self.assertEqual(broken, [])
        self.assertEqual(missing, ['glossary.py not found'])

    def test_the_sources_it_reads_are_the_real_ones(self):
        """The check used to read audit/to_html.py and audit/glossary.py after both
        moved, so it silently took the "skipped" branch for months."""
        src = __import__('pathlib').Path(self.structure.__file__).resolve()
        python_root = src.parent.parent
        self.assertTrue((python_root / 'render' / 'to_html.py').is_file())
        self.assertTrue((python_root / 'render' / 'html_shell.py').is_file())
        self.assertTrue((python_root / 'manuscript' / 'glossary.py').is_file())
        self.assertTrue((python_root / 'manuscript' / 'index.py').is_file())
