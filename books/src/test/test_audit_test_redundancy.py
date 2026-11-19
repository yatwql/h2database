#!/usr/bin/env python3
"""Test-hygiene gate: duplicate bodies, missing assertions, dead cases."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

TAGS = ('layer:audit', 'tier:fast')


class TestRedundancyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, 'test_redundancy')

    def suite(self, name: str, body: str) -> None:
        path = os.path.join(self.tmp.name, name)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)

    def analyse(self) -> list[dict]:
        return self.mod.analyse(self.tmp.name)

    def kinds(self) -> list[str]:
        return [item['kind'] for item in self.analyse()]

    def test_a_single_well_formed_case_is_clean(self):
        self.suite('test_one.py', 'import unittest\n\n\nclass WidgetTest(unittest.TestCase):\n'
                                  '    def test_runs(self):\n'
                                  '        self.assertEqual(1, 1)\n')
        self.assertEqual(self.analyse(), [])

    def test_identical_bodies_are_reported_as_duplicates(self):
        body = ('import unittest\n\n\nclass WidgetTest(unittest.TestCase):\n'
                '    def test_a(self):\n        self.assertEqual(1, 1)\n'
                '    def test_b(self):\n        self.assertEqual(1, 1)\n')
        self.suite('test_dup.py', body)
        self.assertIn('DUPLICATE', self.kinds())

    def test_a_case_without_assertions_is_reported(self):
        self.suite('test_noassert.py', 'import unittest\n\n\n'
                                       'class WidgetTest(unittest.TestCase):\n'
                                       '    def test_silent(self):\n        value = 1\n')
        self.assertIn('NO-ASSERT', self.kinds())

    def test_trivial_body_is_reported(self):
        self.suite('test_trivial.py', 'import unittest\n\n\n'
                                      'class WidgetTest(unittest.TestCase):\n'
                                      '    def test_nothing(self):\n        pass\n')
        self.assertIn('NO-ASSERT', self.kinds())

    def test_test_methods_outside_a_test_case_are_dead(self):
        self.suite('test_dead.py', 'class Helper:\n    def test_stray(self):\n'
                                   '        assert True\n')
        self.assertIn('DEAD', self.kinds())

    def test_shadowed_method_names_are_dead(self):
        self.suite('test_shadow.py', 'import unittest\n\n\n'
                                     'class WidgetTest(unittest.TestCase):\n'
                                     '    def test_a(self):\n        self.assertTrue(True)\n'
                                     '    def test_a(self):\n        self.assertTrue(True)\n')
        self.assertIn('DEAD', self.kinds())

    def test_json_output_reports_the_counts(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn('findings', payload)
        self.assertIn('blocking', payload)

    def test_the_real_suite_is_clean(self):
        code, out = _fixture.run_inproc(BOOK_ROOT, 'test_redundancy.py')
        self.assertEqual(code, 0, out[-600:])


if __name__ == '__main__':
    unittest.main()
