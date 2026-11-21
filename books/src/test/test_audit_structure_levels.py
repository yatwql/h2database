#!/usr/bin/env python3
"""Structure gate: gate levels, appendix-free branches and degraded inputs."""

from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()


class StructureLevelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def chapter(self, name: str = 'ch1-test.md') -> str:
        return os.path.join(self.root, 'data', 'manuscript', name)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def run_gate(self, *args: str):
        return _fixture.run_inproc(self.root, 'structure.py', *args)

    def test_help_prints_the_docstring_and_stops(self):
        code, out = self.run_gate('--help')
        self.assertEqual(code, 0)
        self.assertIn('structure', out.lower())

    def test_a_lower_gate_level_skips_the_expensive_sections(self):
        code, out = self.run_gate('--gate-level', 'p0')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertIn('gate-level: p0', out)

    def test_every_level_is_accepted(self):
        for level in ('p0', 'p1', 'p2'):
            with self.subTest(level=level):
                code, out = self.run_gate('--gate-level', level)
                self.assertIn(code, (0, 1), out[-300:])
                self.assertIn(f'gate-level: {level}', out)

    def test_a_missing_merged_document_is_a_finding_not_a_traceback(self):
        merged = os.path.join(self.root, 'dist', 'test-book.md')
        if os.path.isfile(merged):
            os.remove(merged)
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn('Merged doc not found', out)

    def test_out_of_order_figures_are_counted_not_failed(self):
        path = self.chapter()
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        text += '\n**图 1-3: 后插入的图**\n\n**图 1-2: 再补的图**\n'
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        _code, out = self.run_gate()
        self.assertIn('out-of-order', out)

    def test_a_chapter_with_a_single_reference_is_still_accepted(self):
        path = self.chapter('ch1-test.md')
        self.write('data/manuscript/ch2-test.md',
                   '# 第2章 核心模块\n\n## 2.1 小节\n\n详见第1章《示例总览》。\n')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text.replace('详见第2章《', '详见第1章《'))
        _code, out = self.run_gate()
        self.assertIn('minimal', out)

    def test_a_non_utf8_chapter_is_reported_without_raising(self):
        path = self.chapter()
        with open(path, 'wb') as fh:
            fh.write(b'# \xe7\xac\xac1\xe7\xab\xa0 \xff\xfe broken\n')
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn('UTF-8', out)


if __name__ == '__main__':
    unittest.main()
