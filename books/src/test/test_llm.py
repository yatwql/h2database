#!/usr/bin/env python3
"""Tests for the LLM configuration layer and provider routing."""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, 'lib'))

class PricingAndUsageTest(unittest.TestCase):
    """Every call reports tokens and money, and the number is not a guess."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.llm = _fixture.load_module(self.root, '_llm')

    def test_cost_follows_the_price_file(self):
        with mock.patch.object(self.llm, 'pricing', lambda: {
                'currency': 'USD',
                'models': {'m': {'input_per_mtok': 1.0, 'output_per_mtok': 2.0}}}):
            self.assertAlmostEqual(self.llm.cost_of('m', 1_000_000, 0), 1.0)
            self.assertAlmostEqual(self.llm.cost_of('m', 0, 1_000_000), 2.0)

    def test_an_unpriced_model_says_so_instead_of_guessing(self):
        with mock.patch.object(self.llm, 'pricing', lambda: {'models': {}}):
            self.assertIsNone(self.llm.cost_of('unknown', 10, 10))

    def test_the_estimate_names_prompt_tokens_and_a_cost_range(self):
        guess = self.llm.estimate('x' * 350, 'summary')
        self.assertEqual(guess['prompt_tokens'], 100)
        self.assertGreaterEqual(guess['max_tokens'], 1)
        self.assertIn(guess['currency'], ('USD', 'CNY'))

    def test_a_call_is_recorded_with_tokens_and_money(self):
        log = os.path.join(self.root, 'logs', 'llm-usage.jsonl')
        with mock.patch.object(self.llm, 'usage_log', lambda: log), \
                mock.patch.object(self.llm, 'pricing', lambda: {
                    'currency': 'USD',
                    'models': {'m': {'input_per_mtok': 1.0, 'output_per_mtok': 2.0}}}):
            self.llm._record('p', 'm', 'summary', 1_000_000, 1_000_000)
            line = self.llm.usage_line()
            today = self.llm.today_cost()
        self.assertIn('本次 2000000 token', line)
        self.assertIn('3.0000', line)
        self.assertGreater(today, 0)

    def test_a_dated_model_name_falls_back_to_its_prefix_rule(self):
        table = {'display_currency': 'CNY', 'models': {
            'claude-sonnet-5-': {'input_per_mtok': 2.0, 'output_per_mtok': 10.0,
                                 'currency': 'USD'}}}
        with mock.patch.object(self.llm, 'pricing', lambda: table):
            entry = self.llm.price_of('claude-sonnet-5-5-20260928')
        self.assertEqual(entry['output_per_mtok'], 10.0)

    def test_an_exact_name_beats_the_prefix_rule(self):
        table = {'display_currency': 'CNY', 'models': {
            'claude-sonnet-5-': {'input_per_mtok': 9.0, 'output_per_mtok': 9.0},
            'claude-sonnet-5-5': {'input_per_mtok': 2.0, 'output_per_mtok': 10.0}}}
        with mock.patch.object(self.llm, 'pricing', lambda: table):
            self.assertEqual(self.llm.price_of('claude-sonnet-5-5')['input_per_mtok'], 2.0)

    def test_costs_display_in_cny_by_default(self):
        table = {'display_currency': 'CNY', 'fx': {'CNY': 1.0, 'USD': 7.1},
                 'currency': 'USD',
                 'models': {'m': {'input_per_mtok': 1.0, 'output_per_mtok': 1.0}}}
        with mock.patch.object(self.llm, 'pricing', lambda: table):
            self.assertEqual(self.llm.display_currency(), 'CNY')
            self.assertAlmostEqual(self.llm.convert(1.0, 'USD'), 7.1)
            self.assertEqual(self.llm._money(1.0, 'USD'), '¥7.1000')

    def test_an_unknown_rate_keeps_the_model_currency(self):
        table = {'display_currency': 'CNY', 'fx': {'CNY': 1.0}, 'currency': 'USD',
                 'models': {'m': {'input_per_mtok': 1.0}}}
        with mock.patch.object(self.llm, 'pricing', lambda: table):
            self.assertEqual(self.llm._money(2.5, 'USD'), '2.5000 USD')

    def test_a_multi_call_run_is_summarised_as_a_delta(self):
        with mock.patch.object(self.llm, 'pricing', lambda: {
                'currency': 'USD',
                'models': {'m': {'input_per_mtok': 1.0, 'output_per_mtok': 1.0}}}), \
                mock.patch.object(self.llm, 'usage_log',
                                  lambda: os.path.join(self.tmp.name, 'usage.jsonl')):
            marker = self.llm.take_totals()
            self.llm._record('p', 'm', 'chapter-draft', 10, 10)
            self.llm._record('p', 'm', 'chapter-draft', 10, 10)
            delta = self.llm.since(marker)
            line = self.llm.summary_line(marker)
        self.assertEqual(delta['calls'], 2)
        self.assertEqual(delta['prompt_tokens'], 20)
        self.assertIn('2 次调用', line)

    def test_the_ceiling_warning_appears_only_when_configured_and_reached(self):
        with mock.patch.object(self.llm, 'today_cost', lambda: 5.0), \
                mock.patch.object(self.llm, 'daily_limit', lambda: 0.0):
            self.assertEqual(self.llm.budget_line(), '')
        with mock.patch.object(self.llm, 'today_cost', lambda: 5.0), \
                mock.patch.object(self.llm, 'daily_limit', lambda: 3.0):
            self.assertIn('已达上限', self.llm.budget_line())


class TestLLMRouting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.config_dir = os.path.join(self.root, 'data', 'config')
        os.makedirs(self.config_dir, exist_ok=True)
        with open(os.path.join(self.config_dir, 'llm_provider.json'), 'w', encoding='utf-8') as fh:
            json.dump({'providers': {'mock': {'kind': 'mock'}, 'other': {'kind': 'mock'}},
                       'default_provider': 'mock',
                       'routing': {'scenario': {'summary': 'other'},
                                   'book': {}, 'chapter': {}}}, fh)
        with open(os.path.join(self.config_dir, 'llm_settings.json'), 'w', encoding='utf-8') as fh:
            json.dump({'defaults': {'max_tokens': 100},
                       'scenarios': {'summary': {'max_tokens': 200}},
                       'books': {}, 'chapters': {}}, fh)

    def module(self):
        return _fixture.load_module(self.root, '_llm')

    def test_default_provider(self):
        llm = self.module()
        self.assertEqual(llm.resolve('chapter-draft')['provider'], 'mock')

    def test_scenario_routing(self):
        llm = self.module()
        self.assertEqual(llm.resolve('summary')['provider'], 'other')

    def test_settings_merge(self):
        llm = self.module()
        self.assertEqual(llm.resolve('summary')['settings']['max_tokens'], 200)
        self.assertEqual(llm.resolve('chapter-draft')['settings']['max_tokens'], 100)

    def test_mock_completion(self):
        llm = self.module()
        self.assertIn('mock', llm.complete('提示'))

    def test_missing_config_is_reported(self):
        os.unlink(os.path.join(self.config_dir, 'llm_provider.json'))
        llm = self.module()
        with self.assertRaises(llm.LLMError):
            llm.resolve('summary')

    def test_status_lists_providers(self):
        llm = self.module()
        status = llm.status()
        self.assertEqual(status['default_provider'], 'mock')
        self.assertIn('other', status['providers'])

class TestChannels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def test_status_action(self):
        actions = _fixture.load_module(self.root, 'actions')
        code, text = actions.run('status')
        self.assertEqual(code, 0)
        self.assertIn('chapters', text)

    def test_unknown_action(self):
        actions = _fixture.load_module(self.root, 'actions')
        code, text = actions.run('nope')
        self.assertEqual(code, 2)
        self.assertIn('unknown action', text)

    def test_llm_ask_action(self):
        actions = _fixture.load_module(self.root, 'actions')
        code, text = actions.run('llm-ask', prompt='hello')
        self.assertIn(code, (0, 2))
        self.assertTrue(text.strip())

    def test_tui_once(self):
        code, out = _fixture.run_inproc(self.root, 'tui.py', '--once', 'status')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('chapters', out)

    def test_cli_status(self):
        code, out = _fixture.run_inproc(self.root, 'cli.py', 'status')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('book', out)

if __name__ == '__main__':
    unittest.main()

class TestThinkingLevels(unittest.TestCase):
    """Routing may pin a thinking level per scenario/book/chapter."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.config_dir = os.path.join(self.root, 'data', 'config')
        with open(os.path.join(self.config_dir, 'llm_provider.json'), 'w', encoding='utf-8') as fh:
            json.dump({'providers': {'mock': {'kind': 'mock'}},
                       'default_provider': 'mock',
                       'thinking_levels': ['off', 'low', 'medium', 'high'],
                       'routing': {'scenario': {'summary': {'provider': 'mock',
                                                           'thinking': 'high'},
                                                'review': 'mock'},
                                   'book': {}, 'chapter': {}}}, fh)
        with open(os.path.join(self.config_dir, 'llm_settings.json'), 'w', encoding='utf-8') as fh:
            json.dump({'defaults': {'thinking': 'low'}, 'scenarios': {},
                       'thinking': {'review': 'medium'}, 'books': {}, 'chapters': {}}, fh)

    def module(self):
        return _fixture.load_module(self.root, '_llm')

    def test_scenario_thinking_from_routing(self):
        self.assertEqual(self.module().resolve('summary')['settings']['thinking'], 'high')

    def test_scenario_thinking_from_settings(self):
        self.assertEqual(self.module().resolve('review')['settings']['thinking'], 'medium')

    def test_default_thinking(self):
        self.assertEqual(self.module().resolve('chapter-draft')['settings']['thinking'], 'low')

    def test_mock_reports_thinking(self):
        llm = self.module()
        self.assertIn('high', llm.complete('x', scenario='summary'))

    def test_invalid_thinking_rejected(self):
        llm = self.module()
        prov = os.path.join(self.config_dir, 'llm_provider.json')
        with open(prov, encoding='utf-8') as fh:
            payload = json.load(fh)
        payload['routing']['scenario']['summary']['thinking'] = 'extreme'
        with open(prov, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        with self.assertRaises(llm.LLMError):
            llm.resolve('summary')
