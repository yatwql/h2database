#!/usr/bin/env python3
"""The mutation smoke tool itself: its operators and one end-to-end run."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class MutationSmokeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(_fixture.build_book(self.tmp.name), 'mutation_smoke')

    def test_prose_spans_cover_docstrings_and_comments(self):
        text = '"""doc == not code"""\n# and a comment\nx = 1 == 2\n'
        spans = self.mod._prose_spans(text)
        self.assertTrue(spans)
        candidates = list(self.mod.candidates(text))
        self.assertEqual(len(candidates), 1)          # only the real comparison

    def test_each_operator_produces_a_mutation(self):
        found = self.mod.candidates('a = 1 == 2\nb = True\nc = x and y\n')
        labels = {label for label, _line, _text in found}
        self.assertIn('flip ==', labels)
        self.assertIn('negate True', labels)
        self.assertIn('flip and', labels)

    def test_a_missing_module_or_test_file_is_refused(self):
        self.assertEqual(self.mod.smoke('nope.py', 'test_x.py', 1, 0), 2)
        self.assertEqual(self.mod.smoke('audit/content_volume.py', 'nope.py', 1, 0), 2)

    def test_a_run_reports_whether_a_mutation_survived(self):
        tree = os.path.join(self.tmp.name, 'tree')
        os.makedirs(os.path.join(tree, 'python'), exist_ok=True)
        os.makedirs(os.path.join(tree, 'test'), exist_ok=True)
        with open(os.path.join(tree, 'python', 'tiny.py'), 'w', encoding='utf-8') as fh:
            fh.write('def same(a, b):\n    return a == b\n')
        with open(os.path.join(tree, 'test', 'test_tiny.py'), 'w', encoding='utf-8') as fh:
            fh.write('import unittest\nimport tiny\n\n\n'
                     'class T(unittest.TestCase):\n'
                     '    def test_same(self):\n'
                     '        self.assertTrue(tiny.same(1, 1))\n')
        with mock.patch.object(self.mod, 'SRC', tree):
            code = self.mod.smoke('tiny.py', 'test_tiny.py', 1, 0)
        # `same(1, 1)` is the only case, so flipping `==` to `!=` makes it fail:
        # the mutation is killed and the tool reports success
        self.assertEqual(code, 0)


    def tiny_tree(self, test_body: str) -> str:
        tree = os.path.join(self.tmp.name, 'tree2')
        os.makedirs(os.path.join(tree, 'python'), exist_ok=True)
        os.makedirs(os.path.join(tree, 'test'), exist_ok=True)
        with open(os.path.join(tree, 'python', 'tiny.py'), 'w', encoding='utf-8') as fh:
            fh.write('def same(a, b):\n    return a == b\n')
        with open(os.path.join(tree, 'test', 'test_tiny.py'), 'w', encoding='utf-8') as fh:
            # the copied tree has no conftest, so the test finds the module itself
            fh.write('import os, sys, unittest\n'
                     'sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))\n'
                     'import tiny\n\n\n'
                     'class T(unittest.TestCase):\n'
                     '    def test_x(self):\n' + test_body)
        return tree

    def test_a_test_that_asserts_nothing_lets_the_mutation_survive(self):
        tree = self.tiny_tree('        self.assertEqual(1, 1)\n')
        with mock.patch.object(self.mod, 'SRC', tree):
            code = self.mod.smoke('tiny.py', 'test_tiny.py', 1, 0)
        self.assertEqual(code, 1)        # the flip survived: nothing pinned it

    def test_main_reads_the_flags_and_can_speak_json(self):
        tree = self.tiny_tree('        self.assertTrue(tiny.same(1, 1))\n')
        buffer = io.StringIO()
        with mock.patch.object(self.mod, 'SRC', tree), redirect_stdout(buffer):
            code = self.mod.main(['--module', 'tiny.py', '--tests', 'test_tiny.py',
                                  '--limit', '1', '--json'])
        self.assertEqual(code, 0, buffer.getvalue()[-300:])
        payload = json.loads(buffer.getvalue()[buffer.getvalue().index('{'):])
        self.assertEqual(payload['module'], 'tiny.py')
        self.assertEqual(payload['survived'], [])


if __name__ == '__main__':
    unittest.main()
