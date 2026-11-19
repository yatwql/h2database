#!/usr/bin/env python3
"""Tests for the LLM configuration layer and provider routing."""

import json
import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:infra', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, 'lib'))

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
