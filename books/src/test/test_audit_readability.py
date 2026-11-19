#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""
import os
import sys
import tempfile
import unittest

import _fixture

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def run_script(self, script: str, *args: str):
        return _fixture.run_inproc(self.root, script, *args)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path


class TestReadabilityDeep(FixtureCase):
    def test_unbalanced_box_and_bad_caption(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n'
                   '```text\n┌────────┐\n│ 缺少下边框 │\n```\n\n'
                   '**图 1-1: 架构**\n\n'
                   '**图 1-2: 展示组件 A 与组件 B 的完整调用链路与失败回退**\n')
        code, out = self.run_script('readability.py', '--figures')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertNotIn('Traceback', out)

    def test_wide_diagram_and_long_lines(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n' +
                   '```text\n' + ('x' * 140 + '\n') * 4 + '```\n')
        code, out = self.run_script('readability.py')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertIn('READABILITY', out)


if __name__ == '__main__':
    unittest.main()


class TestReadabilityBranches(FixtureCase):
    def test_runs_on_fixture(self):
        code, out = self.run_script('readability.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_long_sentence_and_wide_diagram(self):
        body = '这是一句' + '很长' * 60 + '的话。\n'
        diagram = '```text\n' + 'x' * 130 + '\n' + 'y' * 130 + '\n' + 'z' * 130 + '\n```\n'
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n' + body + '\n' + diagram)
        code, out = self.run_script('readability.py')
        self.assertIn(code, (0, 1), out[-300:])
