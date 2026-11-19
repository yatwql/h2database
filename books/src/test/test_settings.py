#!/usr/bin/env python3
"""Tests for the writable settings layer and the TUI/CLI surfaces on top of it."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, 'lib'))


class SettingsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def settings(self):
        return _fixture.load_module(self.root, 'settings')

    def read(self, rel: str) -> str:
        with open(os.path.join(self.root, rel), encoding='utf-8') as fh:
            return fh.read()


class TestSettings(SettingsCase):
    def test_list_covers_known_keys(self):
        rows = {row['key'] for row in self.settings().list_settings()}
        self.assertEqual(rows, {'title', 'version', 'manuscript', 'dist',
                                'languages', 'log.level', 'llm.provider'})

    def test_set_title_persists_to_toml(self):
        settings = self.settings()
        settings.set_value('title', '新的书名')
        self.assertIn('title = "新的书名"', self.read('data/tmpl/book.toml'))

    def test_set_dist_persists(self):
        settings = self.settings()
        settings.set_value('dist', 'out')
        self.assertIn('dist = "out"', self.read('data/tmpl/book.toml'))

    def test_set_languages_list(self):
        settings = self.settings()
        self.assertEqual(settings.set_value('languages', 'java, python'), 'java,python')
        payload = json.loads(self.read('data/config/base.json'))
        self.assertEqual(payload['sources']['languages'], ['java', 'python'])

    def test_set_log_level_validates(self):
        settings = self.settings()
        with self.assertRaises(ValueError):
            settings.set_value('log.level', 'LOUD')
        self.assertEqual(settings.set_value('log.level', 'debug'), 'DEBUG')

    def test_set_llm_provider_persists(self):
        settings = self.settings()
        settings.set_value('llm.provider', 'mock')
        payload = json.loads(self.read('data/config/llm_provider.json'))
        self.assertEqual(payload['default_provider'], 'mock')

    def test_empty_value_rejected(self):
        with self.assertRaises(ValueError):
            self.settings().set_value('title', '   ')

    def test_unknown_key_rejected(self):
        with self.assertRaises(KeyError):
            self.settings().set_value('nope', 'x')

    def test_summary_shape(self):
        summary = self.settings().summary()
        for key in ('title', 'version', 'manuscript', 'dist', 'languages',
                    'log_level', 'llm_provider'):
            self.assertIn(key, summary)


class TestTuiSurface(SettingsCase):
    def test_header_shows_identity(self):
        tui = _fixture.load_module(self.root, 'tui')
        text = tui.header()
        self.assertIn('v', text)
        self.assertIn('手稿', text)
        self.assertIn('LLM', text)

    def test_menu_groups(self):
        tui = _fixture.load_module(self.root, 'tui')
        text = tui.menu_text()
        for group in ('内容', '质量', '配置与状态'):
            self.assertIn(group, text)

    def test_once_status_runs(self):
        code, out = _fixture.run_inproc(self.root, 'tui.py', '--once', 'status')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('chapters', out)

    def test_configure_rejects_unknown_choice(self):
        tui = _fixture.load_module(self.root, 'tui')
        answers = iter(['99'])
        with redirect_stdout(io.StringIO()):
            result = tui.configure(reader=lambda _prompt: next(answers))
        self.assertIn('未修改', result)


class TestCliSurface(SettingsCase):
    def test_cli_settings_lists_keys(self):
        code, out = _fixture.run_inproc(self.root, 'cli.py', 'settings')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('llm.provider', out)

    def test_cli_settings_set(self):
        code, out = _fixture.run_inproc(self.root, 'cli.py', 'settings', 'set',
                                        'title', 'CLI 书名')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('CLI 书名', self.read('data/tmpl/book.toml'))

    def test_cli_settings_set_rejects_unknown_key(self):
        code, out = _fixture.run_inproc(self.root, 'cli.py', 'settings', 'set', 'nope', 'x')
        self.assertEqual(code, 2)
        self.assertIn('error', out)


if __name__ == '__main__':
    unittest.main()
