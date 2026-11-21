#!/usr/bin/env python3
"""Order-dependence probe: the comparison logic and a real two-order run."""
from __future__ import annotations

import io
import json
import os
import unittest
from unittest import mock
from contextlib import redirect_stdout

import _fixture

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

TAGS = ('layer:audit', 'tier:slow', 'stability:order')


class OrderComparisonTest(unittest.TestCase):
    def setUp(self):
        self.mod = _fixture.load_module(BOOK_ROOT, 'order_dependence')

    def test_identical_outcomes_are_order_independent(self):
        normal = {'a.test_x': 'ok', 'b.test_y': 'ok'}
        report = self.mod.compare(normal, dict(normal))
        self.assertTrue(report['ok'])
        self.assertEqual(report['order_dependent'], [])

    def test_a_case_that_only_passes_in_one_order_is_reported(self):
        normal = {'a.test_x': 'ok', 'b.test_y': 'fail'}
        reverse = {'a.test_x': 'fail', 'b.test_y': 'ok'}
        report = self.mod.compare(normal, reverse)
        self.assertFalse(report['ok'])
        flagged = {item['test'] for item in report['order_dependent']}
        self.assertEqual(flagged, {'a.test_x', 'b.test_y'})

    def test_skips_are_not_order_dependence(self):
        report = self.mod.compare({'a': 'skip'}, {'a': 'ok'})
        self.assertTrue(report['ok'])

    def test_failure_counts_ignore_skips(self):
        report = self.mod.compare({'a': 'fail', 'b': 'skip'}, {'a': 'fail', 'b': 'ok'})
        self.assertEqual(report['normal_failures'], 1)
        self.assertEqual(report['reverse_failures'], 1)

    def test_collect_returns_one_outcome_per_case(self):
        outcomes = self.mod.collect(only=['test_meta_taxonomy'])
        self.assertTrue(outcomes)
        self.assertTrue(all(value in ('ok', 'fail', 'error', 'skip')
                            for value in outcomes.values()))

    def test_a_small_module_set_is_order_independent(self):
        report = self.mod.run_both(only='test_meta_taxonomy,test_audit_version_consistency')
        self.assertTrue(report['ok'], report)

    def test_outcomes_are_keyed_by_test_id(self):
        outcomes = self.mod.collect(only=['test_meta_taxonomy'])
        self.assertTrue(all('(' not in name for name in outcomes),
                        f'expected dotted ids, got {list(outcomes)[:2]}')
        self.assertTrue(any(name.startswith('test_meta_taxonomy.') for name in outcomes))

    def test_bisect_reports_a_target_that_passes_in_full_order(self):
        result = self.mod.bisect(
            'test_meta_taxonomy',
            pool=['test_audit_version_consistency', 'test_meta_taxonomy'])
        self.assertTrue(result['ok'])
        self.assertEqual(result.get('prefix', []), [])

    def test_bisect_refuses_a_target_that_only_fails_alone(self):
        with mock.patch.object(self.mod, 'run_prefix', return_value='fail'):
            result = self.mod.bisect('test_meta_taxonomy')
        self.assertFalse(result['ok'])
        self.assertIn('not order-dependent', result['reason'])

    def test_json_output_is_parseable(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--only', 'test_meta_taxonomy', '--json'])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload['ok'])


if __name__ == '__main__':
    unittest.main()
