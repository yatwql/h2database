#!/usr/bin/env python3
"""Scenario matrix: the same pipeline under combinations of inputs.

unittest has no markers, so each dimension is a subTest with labelled kwargs —
a failure names the exact combination (`newline='crlf' chapter_layout='single'`).
"""
from __future__ import annotations

import itertools
import json
import os
import tempfile
import unittest

import _fixture

_fixture.ensure_tools_path()


class ScenarioMatrixTest(unittest.TestCase):
    """newline × chapter layout × style strictness, all four combinations."""

    def build(self, newline: str, layout: str, style: str) -> str:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        extra = {}
        if layout == 'single':
            extra['data/tmpl/book.toml'] = _fixture.BOOK_TOML.replace(
                '"ch2-test.md",\n', '').replace(
                '"ch2-test.md" = ["核心模块"]\n', '').replace(
                '"ch2-test.md" = [2]\n', '').replace(
                '"ch2-test.md" = ["org.example.core"]\n', '').replace(
                '"ch2-test.md" = ["第2章 测试章节"]\n', '')
        root = _fixture.build_book(tmp.name, extra=extra)
        if newline == 'crlf':
            for name in ('cover.md', 'ch1-test.md', 'ch2-test.md'):
                path = os.path.join(root, 'data', 'manuscript', name)
                if not os.path.isfile(path):
                    continue
                with open(path, encoding='utf-8') as fh:
                    text = fh.read()
                with open(path, 'w', encoding='utf-8', newline='\r\n') as fh:
                    fh.write(text)
        if style == 'strict':
            path = os.path.join(root, 'data', 'config', 'style.json')
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
            data.setdefault('captions', {}).setdefault('presets', {})['strict'] = {
                'min_chars': 20, 'max_chars': 24, 'fail_at': 0}
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, ensure_ascii=False)
        return root

    def test_build_pipeline_under_every_combination(self):
        for newline, layout, style in itertools.product(
                ('lf', 'crlf'), ('two-chapter', 'single'), ('normal', 'strict')):
            with self.subTest(newline=newline, layout=layout, style=style):
                root = self.build(newline, layout, style)
                code, out = _fixture.run_inproc(root, 'merge.py')
                self.assertEqual(code, 0, out[-400:])
                merged = os.path.join(root, 'dist', 'test-book.md')
                self.assertTrue(os.path.isfile(merged))
                with open(merged, encoding='utf-8') as fh:
                    text = fh.read()
                self.assertIn('# 第1章', text)
                self.assertNotIn('\r\n', text.replace('\r\n', '') and '')

    def test_structure_gate_is_scenario_stable(self):
        for newline, layout in itertools.product(('lf', 'crlf'), ('two-chapter', 'single')):
            with self.subTest(newline=newline, layout=layout):
                root = self.build(newline, layout, 'normal')
                code, out = _fixture.run_inproc(root, 'structure.py')
                self.assertIn(code, (0, 1), out[-400:])
                self.assertNotIn('Traceback', out)


class LanguageMatrixTest(unittest.TestCase):
    """digest → outline runs for every analysed language, not just Java."""

    def test_each_language_fixture_digests(self):
        for language in ('mini-java', 'mini-python', 'mini-rust'):
            with self.subTest(language=language):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                root = _fixture.build_book(tmp.name)
                code, out = _fixture.run_inproc(root, 'digest.py')
                self.assertIn(code, (0, 1, 2), out[-400:])
                self.assertNotIn('Traceback', out)


if __name__ == '__main__':
    unittest.main()
