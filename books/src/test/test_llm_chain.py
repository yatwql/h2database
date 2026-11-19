#!/usr/bin/env python3
"""Priority chain, fallback and endpoint pacing (no network, no real sleeping)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class ChainCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.llm = _fixture.load_module(self.root, '_llm')
        config = self.llm.providers()
        config['providers'] = {
            'primary': {'kind': 'openai-compatible', 'base_url': 'https://a.invalid/v1',
                        'api_key_env': 'PRIMARY_KEY', 'models': ['m1'], 'priority': 10,
                        'pacing': {'min_interval': 5, 'max_concurrency': 1}},
            'secondary': {'kind': 'openai-compatible', 'base_url': 'https://b.invalid/v1',
                          'api_key_env': 'SECONDARY_KEY', 'models': ['m2'], 'priority': 20},
            'backup': {'kind': 'mock', 'priority': 90},
        }
        config['default_provider'] = 'primary'
        config['routing'] = {'scenario': {}, 'book': {}, 'chapter': {}}
        patch = mock.patch.object(self.llm, 'providers', return_value=config)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(mock.patch.stopall)
        os.environ.pop('PRIMARY_KEY', None)
        os.environ.pop('SECONDARY_KEY', None)

    def test_order_prefers_the_routed_provider_then_priority(self):
        self.assertEqual(self.llm._ordered_providers('primary'),
                         ['primary', 'secondary', 'backup'])
        self.assertEqual(self.llm._ordered_providers('backup'),
                         ['backup', 'primary', 'secondary'])

    def test_falls_back_when_the_first_provider_fails(self):
        os.environ['SECONDARY_KEY'] = 'k'
        self.addCleanup(os.environ.pop, 'SECONDARY_KEY', None)

        def transport(url, payload, api_key, timeout, headers=None):
            if 'a.invalid' in url:
                raise self.llm.LLMError('primary down')
            return {'choices': [{'message': {'content': '备用回答'}}]}

        with mock.patch.object(self.llm, '_post_json', side_effect=transport):
            self.assertEqual(self.llm.complete('hi'), '备用回答')

    def test_missing_keys_fall_through_to_the_next_provider(self):
        answer = self.llm.complete('hi')  # primary/secondary lack keys -> mock backup
        self.assertIn('mock', answer)

    def test_all_failures_raise_with_the_last_error(self):
        config = self.llm.providers()
        config['providers'] = {
            'primary': {'kind': 'openai-compatible', 'base_url': 'https://a.invalid/v1',
                        'api_key_env': 'PRIMARY_KEY', 'priority': 10},
        }
        with mock.patch.object(self.llm, 'providers', return_value=config), \
                self.assertRaises(self.llm.LLMError) as ctx:
            self.llm.complete('hi')
        self.assertIn('all providers failed', str(ctx.exception))

    def test_pacing_waits_the_declared_interval(self):
        spec = {'pacing': {'min_interval': 5}}
        clock = iter([100.0, 100.0, 102.0, 105.0])
        with mock.patch.object(self.llm.time, 'monotonic', side_effect=lambda: next(clock)), \
                mock.patch.object(self.llm.time, 'sleep') as sleep:
            self.llm._respect_pacing('primary', spec)
            self.llm._respect_pacing('primary', spec)
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args[0][0], 3.0)

    def test_pacing_without_interval_never_sleeps(self):
        with mock.patch.object(self.llm.time, 'sleep') as sleep:
            self.llm._respect_pacing('primary', {})
        sleep.assert_not_called()

    def test_status_reports_the_priority_order(self):
        status = self.llm.status()
        self.assertEqual(status['default_provider'], 'primary')
        self.assertEqual(sorted(status['providers']), ['backup', 'primary', 'secondary'])


if __name__ == '__main__':
    unittest.main()
