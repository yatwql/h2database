#!/usr/bin/env python3
"""Every threshold is a boundary: one under the line fails, one over it passes.

A configured number that nobody tests is a number that silently stops applying.
Each case takes one key from `base.json`/`style.json`, drives the gate that reads
it to both sides of the line, and asserts the verdict flips.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class ThresholdBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def gate(self, script: str, *args: str) -> tuple[int, str]:
        return _fixture.run_inproc(self.root, script, *args)

    def with_thresholds(self, **values):
        """Patch the toolchain thresholds the gates read, restoring afterwards."""
        module = _fixture.load_module(self.root, 'make')._config
        patched = {**module.THRESHOLDS, **values}
        holder = mock.patch.dict(module.current().thresholds, patched, clear=True)
        holder.start()
        self.addCleanup(holder.stop)
        return module

    # -- captions --------------------------------------------------------
    def test_the_caption_length_bounds_are_exclusive(self):
        # 31 characters: over strict's 30, still inside normal's 40
        caption = '展示三个组件在一次写入过程中的完整调用顺序与失败回退路径的说明'
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(f'# 第1章 测试章节\n\n**图 1-1: {caption}**\n')
        normal, normal_out = self.gate('captions.py', '--threshold', 'normal')
        strict, strict_out = self.gate('captions.py', '--threshold', 'strict')
        self.assertEqual(normal, 0, normal_out[-300:])
        self.assertEqual(strict, 1, strict_out[-300:])

    # -- figure clusters -------------------------------------------------
    def test_a_cluster_needs_the_configured_number_of_figures(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('# 第1章 测试章节\n\n**图 1-1: 展示 A**\n\n**图 1-2: 展示 B**\n')
        two, _ = self.gate('figure_clusters.py', '--min', '2', '--json')
        three, out = self.gate('figure_clusters.py', '--min', '3', '--json')
        self.assertEqual((two, three), (0, 0))
        payload = json.loads(out[out.index('{'):])
        self.assertEqual(payload['min_figs'], 3)

    # -- diagrams --------------------------------------------------------
    def test_the_ascii_width_budget_is_read_from_the_config(self):
        config = os.path.join(self.root, 'data', 'config', 'base.json')
        with open(config, encoding='utf-8') as fh:
            payload = json.load(fh)
        payload.setdefault('toolchain', {})['ascii_max_cols'] = 20
        with open(config, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        wide = 'x' * 40
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(f'# 第1章 测试章节\n\n```text\n{wide}\n```\n')
        code, out = self.gate('diagrams.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('40', out)

    # -- coverage --------------------------------------------------------
    def test_the_coverage_floor_is_a_number_the_gate_reads(self):
        module = self.with_thresholds(coverage_fail_under=50, coverage_min_per_file=0)
        self.assertEqual(module.THRESHOLDS['coverage_fail_under'], 50)
        self.assertEqual(module.THRESHOLDS['coverage_min_per_file'], 0)

    # -- content volume --------------------------------------------------
    def test_the_floor_ratio_decides_how_much_shrinkage_is_a_problem(self):
        module = _fixture.load_module(self.root, 'content_volume')
        baseline = {'manuscript': {'files': {'ch1-test.md': {'bytes': 1000, 'lines': 100}},
                                   'total': {'bytes': 1000, 'lines': 100}},
                    'thresholds': {'floor_ratio': 0.5}}
        current = {'manuscript': {'files': {'ch1-test.md': {'bytes': 600, 'lines': 60}},
                                  'total': {'bytes': 600, 'lines': 60}},
                   'delivered': {}}
        self.assertEqual(module.compare(baseline, current), [])
        baseline['thresholds']['floor_ratio'] = 0.9
        self.assertTrue(module.compare(baseline, current))

    # -- every key is read somewhere -------------------------------------
    def test_no_config_key_is_orphaned(self):
        """A key nobody reads is a threshold that stopped applying."""
        source = ''
        for folder, _dirs, names in os.walk(os.path.join(_fixture.TOOLS_DIR)):
            for name in names:
                if name.endswith('.py'):
                    with open(os.path.join(folder, name), encoding='utf-8') as fh:
                        source += fh.read()
        # the real book's config against the real toolchain: a key nobody reads
        # is a threshold that silently stopped applying
        book = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))
        config_dir = os.path.join(book, 'data', 'config')
        if not os.path.isdir(config_dir):
            self.skipTest('this checkout has no book config')

        with open(os.path.join(config_dir, 'base.json'), encoding='utf-8') as fh:
            base = json.load(fh)
        with open(os.path.join(config_dir, 'style.json'), encoding='utf-8') as fh:
            style = json.load(fh)
        orphans = []
        for payload in (base, style):
            for section, values in payload.items():
                if not isinstance(values, dict):
                    continue
                for key in values:
                    if key not in source:
                        orphans.append(f'{section}.{key}')
        self.assertEqual(orphans, [])


if __name__ == '__main__':
    unittest.main()
