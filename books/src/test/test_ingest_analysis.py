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


class TestAnalysisBranches(FixtureCase):
    def test_balance_check_json_and_baseline(self):
        code, out = self.run_script('balance.py', '--json')
        self.assertIn(code, (0, 1), out[-200:])
        baseline = os.path.join(self.root, 'dist', 'baseline.json')
        code, _ = self.run_script('balance.py', '--baseline', baseline)
        self.assertEqual(code, 0)
        code, out = self.run_script('balance.py', '--diff', baseline)
        self.assertEqual(code, 0, out[-200:])

    def test_balance_check_missing_baseline(self):
        code, out = self.run_script('balance.py', '--diff',
                                    os.path.join(self.root, 'nope.json'))
        self.assertEqual(code, 1)
        self.assertIn('基线文件不存在', out)


if __name__ == '__main__':
    unittest.main()
