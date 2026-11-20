#!/usr/bin/env python3
"""Requirement trace: every requirement has one judgement row, carriers exist."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

class RequirementTraceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, 'requirement_trace')

    def rows(self, *specs: tuple[str, str]) -> list[tuple[str, str, int]]:
        return [(identifier, cell, index + 1)
                for index, (identifier, cell) in enumerate(specs)]

    # -- coverage ---------------------------------------------------------
    def test_a_requirement_without_a_row_is_reported(self):
        findings = self.mod.check(['FR-01', 'FR-02'],
                                  self.rows(('FR-01', '`structure.py`')),
                                  {'structure.py'})
        self.assertEqual([f['kind'] for f in findings], ['TRACE'])
        self.assertIn('FR-02', findings[0]['detail'])

    def test_a_row_for_an_undeclared_requirement_is_reported(self):
        findings = self.mod.check(['FR-01'],
                                  self.rows(('FR-01', '`structure.py`'),
                                            ('FR-09', '`structure.py`')),
                                  {'structure.py'})
        self.assertEqual(len(findings), 1)
        self.assertIn('FR-09', findings[0]['detail'])

    def test_a_requirement_traced_twice_is_reported(self):
        findings = self.mod.check(['FR-01'],
                                  self.rows(('FR-01', '`structure.py`'),
                                            ('FR-01', '`links.py`')),
                                  {'structure.py', 'links.py'})
        self.assertEqual([f['kind'] for f in findings], ['TRACE'])
        self.assertIn('twice', findings[0]['detail'])

    # -- carriers ---------------------------------------------------------
    def test_a_carrier_that_does_not_exist_is_reported(self):
        findings = self.mod.check(['FR-01'],
                                  self.rows(('FR-01', '`no_such_gate.py`')),
                                  set())
        self.assertIn('no_such_gate.py', findings[0]['detail'])

    def test_an_existing_carrier_passes(self):
        self.assertEqual(self.mod.check(['FR-01'],
                                        self.rows(('FR-01', '`structure.py`')),
                                        {'structure.py'}), [])

    def test_a_manual_marker_counts_as_a_carrier(self):
        self.assertEqual(self.mod.check(['FR-12'],
                                        self.rows(('FR-12', '人工复核')),
                                        set()), [])

    def test_a_row_without_carrier_or_marker_is_reported(self):
        findings = self.mod.check(['FR-01'], self.rows(('FR-01', '待定')), set())
        self.assertIn('names no carrier', findings[0]['detail'])

    # -- real documents ---------------------------------------------------
    def test_the_repository_traces_every_requirement(self):
        declared = self.mod.requirement_ids()
        self.assertTrue(declared)
        self.assertEqual(self.mod.check(declared), [])

    # -- CLI --------------------------------------------------------------
    def test_json_output_lists_the_requirements(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload['requirements'])
        self.assertEqual(payload['count'], 0)

    def test_human_output_states_the_verdict(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([])
        self.assertEqual(code, 0)
        self.assertIn('可追溯', buffer.getvalue())

if __name__ == '__main__':
    unittest.main()
