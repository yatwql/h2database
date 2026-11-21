#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:audit', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

HAS_PYPDF = importlib.util.find_spec('pypdf') is not None

class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

class TestFigureClusterHelpers(FixtureCase):
    FIGURES = (
        '展示三个组件之间的调用关系与数据流向。\n\n'
        '**图 1-1: 展示组件 A 的调用**\n\n'
        '**图 1-2: 展示组件 B 的调用**\n\n'
        '**图 1-3: 展示组件 C 的调用**\n'
    )

    def test_find_clusters_with_bridge(self):
        clusters = self.module('figure_clusters')
        path = self.write('data/manuscript/cluster.md', self.FIGURES)
        found = clusters.find_clusters(path, min_figs=3, window=40)
        self.assertEqual(len(found), 1)

    def test_find_clusters_without_bridge(self):
        clusters = self.module('figure_clusters')
        path = self.write('data/manuscript/cluster2.md',
                          '**图 2-1: 展示 A**\n\n**图 2-2: 展示 B**\n\n**图 2-3: 展示 C**\n')
        found = clusters.find_clusters(path, min_figs=3, window=40)
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]['bridged'])

    def test_window_default_comes_from_the_config(self):
        clusters = self.module('figure_clusters')
        patched = dict(clusters._config.STYLE_POLICY)
        patched['clusters'] = {'min_figures': 2, 'window_lines': 12}
        with mock.patch.object(clusters._config, 'STYLE_POLICY', patched), \
             mock.patch.object(clusters, 'MS_DIR', os.path.join(self.root, 'data', 'manuscript')), \
             mock.patch('sys.stdout', new=io.StringIO()) as out:
            clusters.main(['--json'])
        payload = json.loads(out.getvalue())
        self.assertEqual(payload['window_lines'], 12)
        self.assertEqual(payload['min_figs'], 2)

    def test_no_cluster_below_threshold(self):
        clusters = self.module('figure_clusters')
        path = self.write('data/manuscript/single.md', '**图 3-1: 展示 A**\n')
        self.assertEqual(clusters.find_clusters(path, min_figs=3, window=40), [])

if __name__ == '__main__':
    unittest.main()
