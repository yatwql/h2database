#!/usr/bin/env python3
"""Tests for the symbol-drift baseline logic in source_freshness_check."""
import importlib
import json
import os
import sys
import tempfile
import unittest
from collections import namedtuple

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

sfc = importlib.import_module('source_freshness_check')

Claim = namedtuple('Claim', 'doc_file doc_line class_name method')


class BaselineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.baseline = os.path.join(self.tmp.name, 'baseline.json')

    def test_missing_baseline_is_empty(self):
        data = sfc.load_baseline(self.baseline)
        self.assertEqual(data['accepted'], [])
        self.assertEqual(data['h2_version'], '')

    def test_save_then_load_roundtrip(self):
        broken = [(Claim('ch3.md', 10, 'MVMap', 'rollbackTo'), 'org/h2/mvstore/MVMap.java')]
        sfc.save_baseline(broken, '2.4.249-SNAPSHOT', self.baseline)
        data = sfc.load_baseline(self.baseline)
        self.assertEqual(data['h2_version'], '2.4.249-SNAPSHOT')
        self.assertEqual(data['accepted'], ['ch3.md::MVMap::rollbackTo'])

    def test_baseline_is_sorted_and_stable(self):
        broken = [
            (Claim('b.md', 1, 'Zeta', 'm1'), 'x'),
            (Claim('a.md', 2, 'Alpha', 'm2'), 'x'),
        ]
        sfc.save_baseline(broken, 'v1', self.baseline)
        with open(self.baseline, encoding='utf-8') as fh:
            payload = json.load(fh)
        self.assertEqual(payload['accepted'], sorted(payload['accepted']))

    def test_corrupt_baseline_degrades_gracefully(self):
        with open(self.baseline, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        self.assertEqual(sfc.load_baseline(self.baseline)['accepted'], [])


class DriftClassificationTest(unittest.TestCase):
    def test_split_known_and_new(self):
        baseline = {'accepted': ['ch3.md::MVMap::rollbackTo']}
        broken = [
            (Claim('ch3.md', 5, 'MVMap', 'rollbackTo'), 'a'),
            (Claim('ch4.md', 9, 'Session', 'checkDeadlock'), 'b'),
        ]
        new, known = sfc.split_drift(broken, baseline)
        self.assertEqual([c.method for c, _ in new], ['checkDeadlock'])
        self.assertEqual([c.method for c, _ in known], ['rollbackTo'])

    def test_empty_baseline_marks_everything_new(self):
        new, known = sfc.split_drift([(Claim('a.md', 1, 'A', 'm'), 'x')], {'accepted': []})
        self.assertEqual(len(new), 1)
        self.assertEqual(known, [])


class SuggestRenamesTest(unittest.TestCase):
    def test_suggests_close_method_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'MVMap.java')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write('class MVMap { void rollbackRoot() {} void setRootPos() {} }')
            hints = sfc.suggest_renames(Claim('ch.md', 1, 'MVMap', 'rollbackTo'),
                                        {'MVMap': [path]})
        self.assertIn('rollbackRoot', hints)

    def test_unknown_class_returns_no_hints(self):
        self.assertEqual(
            sfc.suggest_renames(Claim('ch.md', 1, 'Nope', 'x'), {}), []
        )

    def test_ambiguous_class_returns_no_hints(self):
        claim = Claim('ch.md', 1, 'Dup', 'x')
        self.assertEqual(sfc.suggest_renames(claim, {'Dup': ['a.java', 'b.java']}), [])


if __name__ == '__main__':
    unittest.main()
