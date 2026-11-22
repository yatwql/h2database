#!/usr/bin/env python3
"""Baseline plumbing: path resolution, tolerant loading, save and split."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()


class BaselineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        # lib/_baseline.py uses relative imports, so load it as part of the package
        self.mod = importlib.import_module('lib._baseline')
        # point the module at the fixture book without touching the shared config
        patches = (mock.patch.object(self.mod._config, 'BOOK_ROOT', self.root),
                   mock.patch.object(self.mod, 'BASELINE_DIR',
                                     os.path.join(self.root, 'data', 'baselines')))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_configured_baseline_wins_over_the_default_name(self):
        path = self.mod.path_for('source_symbol')
        self.assertIn('source-symbol-baseline.json', path.replace('_', '-'))

    def test_an_unconfigured_gate_falls_back_to_findings_json(self):
        self.assertTrue(self.mod.path_for('whatever').endswith('whatever-findings.json'))

    def test_a_missing_baseline_loads_as_empty(self):
        self.assertEqual(self.mod.load('whatever'), set())

    def test_a_broken_baseline_does_not_crash_the_gate(self):
        path = self.mod.path_for('whatever')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        self.assertEqual(self.mod.load('whatever'), set())

    def test_save_and_load_round_trip(self):
        saved = self.mod.save('whatever', {'b', 'a'}, note='reviewed')
        self.assertEqual(self.mod.load('whatever'), {'a', 'b'})
        with open(saved, encoding='utf-8') as fh:
            payload = json.load(fh)
        self.assertEqual(payload['note'], 'reviewed')
        self.assertEqual(payload['accepted'], ['a', 'b'])

    def test_split_separates_new_from_stale(self):
        self.mod.save('whatever', {'old'}, note='x')
        new, stale = self.mod.split('whatever', {'old', 'fresh'})
        self.assertEqual(new, {'fresh'})
        self.assertEqual(stale, set())
        new, stale = self.mod.split('whatever', set())
        self.assertEqual((new, stale), (set(), {'old'}))


if __name__ == '__main__':
    unittest.main()
