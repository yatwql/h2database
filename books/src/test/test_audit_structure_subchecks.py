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
