#!/usr/bin/env python3
"""Figure clusters: cluster detection, bridging and the report modes."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

class FigureClusterModesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(self.path, 'w', encoding='utf-8') as fh:
            fh.write('# 第1章 测试\n\n'
                     '**图 1-1: 展示组件的连接方式**\n\n'
                     '**图 1-2: 展示组件的调用顺序**\n\n'
                     '**图 1-3: 展示组件的失败回退**\n')

    def run_gate(self, *args: str) -> tuple[int, str]:
        return _fixture.run_inproc(self.root, 'figure_clusters.py', *args)

    def test_table_report_lists_the_cluster(self):
        code, out = self.run_gate()
        self.assertEqual(code, 0, out[-400:])
        self.assertIn('图簇检测', out)
        self.assertIn('待桥接', out)

    def test_json_payload_carries_the_counts(self):
        code, out = self.run_gate('--json')
        self.assertEqual(code, 0, out[-400:])
        payload = json.loads(out[out.index('{'):])
        self.assertIn('total_clusters', payload)
        self.assertIn('unbridged', payload)
        self.assertGreaterEqual(payload['total_clusters'], 1)

    def test_needs_bridge_filter_shows_unbridged_only(self):
        code, out = self.run_gate('--needs-bridge')
        self.assertEqual(code, 0)
        self.assertIn('待桥接', out)
        self.assertNotIn('✓ 已桥接', out)

    def test_has_bridge_filter_is_silent_without_bridges(self):
        code, out = self.run_gate('--has-bridge')
        self.assertEqual(code, 0)
        self.assertNotIn('figs:', out)  # no cluster rows listed

if __name__ == '__main__':
    unittest.main()
