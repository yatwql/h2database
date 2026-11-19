#!/usr/bin/env python3
"""Captions gate: JSON output, baseline diff and the failure threshold."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

class CaptionsBaselineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_captions(self, *args: str) -> tuple[int, str]:
        return _fixture.run_inproc(self.root, 'captions.py', *args)

    def baseline(self, payload: dict) -> str:
        path = os.path.join(self.tmp.name, 'captions.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return path

    def test_json_output_has_the_expected_shape(self):
        code, out = self.run_captions('--json')
        payload = json.loads(out[out.index('{'):])
        self.assertIn(code, (0, 1))
        for key in ('threshold', 'count', 'violations'):
            self.assertIn(key, payload)

    def test_diff_reports_new_and_fixed_entries(self):
        baseline = self.baseline({'count': 1, 'violations': [
            {'file': 'ch1-test.md', 'fig_id': '1-1', 'reason': 'old'}]})
        code, out = self.run_captions('--diff', baseline)
        self.assertEqual(code, 0, out[-400:])
        self.assertIn('与基线比较', out)
        self.assertIn('已修复', out)

    def test_diff_with_a_corrupt_baseline_exits_two(self):
        path = os.path.join(self.tmp.name, 'bad.json')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        code, out = self.run_captions('--diff', path)
        self.assertEqual(code, 2, out[-400:])

    def test_diff_with_a_missing_baseline_exits_two(self):
        code, out = self.run_captions('--diff', os.path.join(self.tmp.name, 'none.json'))
        self.assertEqual(code, 2, out[-400:])

    def test_strict_threshold_fails_on_a_violating_caption(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text.replace('**图 1-1: 展示组件 A 的连接方式**',
                                  '**图 1-1: 对比**'))
        code, out = self.run_captions('--threshold', 'strict')
        self.assertEqual(code, 1, out[-400:])

    def test_normal_threshold_tolerates_the_fixture(self):
        code, out = self.run_captions('--threshold', 'normal')
        self.assertIn(code, (0, 1), out[-300:])

if __name__ == '__main__':
    unittest.main()
