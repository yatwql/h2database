#!/usr/bin/env python3
"""Structure gate: each invariant is proven by mutating a healthy book."""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

_fixture.ensure_tools_path()


class StructureMutationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def chapter(self, name: str = 'ch1-test.md') -> str:
        return os.path.join(self.root, 'data', 'manuscript', name)

    def mutate(self, name: str, old: str, new: str) -> None:
        path = self.chapter(name)
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn(old, text, f'mutation anchor missing in {name}')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text.replace(old, new, 1))

    def run_gate(self):
        return _fixture.run_inproc(self.root, 'structure.py')

    def test_healthy_fixture_passes(self):
        code, out = self.run_gate()
        self.assertIn(code, (0, 1), out[-400:])

    def test_figure_number_gap_is_reported(self):
        self.mutate('ch2-test.md', '**图 2-1:', '**图 2-3:')
        code, out = self.run_gate()
        self.assertIn(code, (0, 1))
        self.assertIn('Figure Numbering', out)

    def test_duplicate_figure_number_is_reported(self):
        self.mutate('ch1-test.md', '**图 1-1:', '**图 2-1:')
        _code, out = self.run_gate()
        self.assertTrue(out)

    def test_unbalanced_code_fence_is_reported(self):
        self.mutate('ch1-test.md', '```text\n', '```text\n```text\n')
        _code, out = self.run_gate()
        self.assertIn('Code Fence', out)

    def test_broken_cross_reference_is_reported(self):
        self.mutate('ch1-test.md', '详见第2章《第2章 测试章节》。', '详见第9章《不存在》。')
        _code, out = self.run_gate()
        self.assertIn('9', out)

    def test_missing_required_section_is_reported(self):
        self.mutate('ch1-test.md', '## 1.10 延伸思考', '## 1.10 别的标题')
        _code, out = self.run_gate()
        self.assertIn('延伸思考', out)

    def test_heading_level_jump_is_reported(self):
        self.mutate('ch1-test.md', '## 1.1 小节', '#### 1.1 小节')
        _code, out = self.run_gate()
        self.assertTrue(out)

    def test_structure_runs_after_a_full_build(self):
        """HTML/merged/TOC checks only execute when the artifacts exist."""
        for script in ('cover.py', 'merge.py', 'to_html.py'):
            code, out = _fixture.run_inproc(self.root, script)
            self.assertEqual(code, 0, out[-400:])
        code, out = self.run_gate()
        self.assertIn(code, (0, 1), out[-600:])
        self.assertIn('CSS', out)
        self.assertIn('Merged', out)

    def test_stale_merged_document_is_reported(self):
        _fixture.run_inproc(self.root, 'merge.py')
        merged = os.path.join(self.root, 'dist', 'test-book.md')
        with open(merged, 'a', encoding='utf-8') as fh:
            fh.write('\n手工追加的一行，会让合并稿与章节不一致。\n')
        _code, out = self.run_gate()
        self.assertIn('Merged', out)


if __name__ == '__main__':
    unittest.main()
