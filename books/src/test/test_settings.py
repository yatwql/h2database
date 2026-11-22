#!/usr/bin/env python3
"""Tests for the writable settings layer and the TUI/CLI surfaces on top of it."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

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

class HeaderGlanceTest(SettingsCase):
    """The header answers "how much left" without running an action."""

    def test_summary_carries_spend_and_volume_margin(self):
        summary = self.settings().summary()
        self.assertIn('llm_spend', summary)
        self.assertIn('volume_margin', summary)

    def test_the_spend_line_uses_the_display_currency(self):
        summary = self.settings().summary()
        self.assertTrue(summary['llm_spend'].startswith('¥')
                        or summary['llm_spend'] == '—', summary['llm_spend'])

    def test_a_book_without_a_baseline_says_dash(self):
        summary = self.settings().summary()
        self.assertEqual(summary['volume_margin'], '—')

    def test_the_margin_names_lines_and_both_counts(self):
        room = {'lines': 40097, 'baseline': 36893, 'floor': 35048, 'margin_pct': 14.4}
        settings = self.settings()
        with mock.patch.object(settings._volume, 'headroom', lambda: room):
            text = settings.volume_summary()
        self.assertIn('行', text)
        self.assertIn('下限', text)
        self.assertIn('40,097', text)
        self.assertIn('+14%', text)

    def test_the_volume_margin_is_measured_against_the_floor(self):
        volume = _fixture.load_module(self.root, '_volume')
        baseline = {'manuscript': {'total': {'lines': 100}},
                    'thresholds': {'floor_ratio': 0.95}}
        path = os.path.join(self.root, 'data', 'baselines')
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, 'content-volume.json'), 'w', encoding='utf-8') as fh:
            json.dump(baseline, fh)
        current = volume.current_lines()
        room = volume.headroom()
        self.assertEqual(room['baseline'], 100)
        self.assertEqual(room['lines'], current)
        self.assertEqual(room['floor'], 95)


class TestSettings(SettingsCase):
    def test_list_covers_known_keys(self):
        rows = {row['key'] for row in self.settings().list_settings()}
        self.assertEqual(rows, {'title', 'version', 'manuscript', 'dist',
                                'languages', 'log.level', 'llm.provider',
                                'llm.daily_cost_limit', 'llm.ingest_prose'})

    def test_set_title_persists_to_toml(self):
        settings = self.settings()
        settings.set_value('title', '新的书名')
        self.assertIn('title = "新的书名"', self.read('data/config/book/book.toml'))

    def test_set_dist_persists(self):
        settings = self.settings()
        settings.set_value('dist', 'out')
        self.assertIn('dist = "out"', self.read('data/config/book/book.toml'))

    def test_set_languages_list(self):
        settings = self.settings()
        self.assertEqual(settings.set_value('languages', 'java, python'), 'java,python')
        payload = json.loads(self.read('data/config/base.json'))
        self.assertEqual(payload['sources']['languages'], ['java', 'python'])

    def test_set_ingest_prose_writes_a_toml_boolean(self):
        settings = self.settings()
        self.assertEqual(settings.set_value('llm.ingest_prose', 'true'), 'true')
        with open(os.path.join(self.root, 'data', 'config', 'book', 'book.toml'),
                  encoding='utf-8') as fh:
            body = fh.read()
        self.assertIn('ingest_prose = true', body)
        self.assertEqual(settings.get('llm.ingest_prose'), 'true')

    def test_a_bad_boolean_is_refused(self):
        with self.assertRaises(ValueError):
            self.settings().set_value('llm.ingest_prose', 'maybe')

    def test_the_daily_cost_limit_is_writable_and_non_negative(self):
        settings = self.settings()
        self.assertEqual(settings.set_value('llm.daily_cost_limit', '3'), '3.0')
        self.assertEqual(settings.get('llm.daily_cost_limit'), '3.0')
        with self.assertRaises(ValueError):
            settings.set_value('llm.daily_cost_limit', '-1')

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

    def test_the_frequent_actions_sit_on_the_first_level(self):
        tui = _fixture.load_module(self.root, 'tui')
        text = tui.menu_text('main')
        for label in ('源码 → 手稿', '手稿 → Markdown + HTML', '质量', '配置'):
            self.assertIn(label, text)

    def test_every_second_level_screen_offers_back(self):
        tui = _fixture.load_module(self.root, 'tui')
        for screen in ('quality', 'config'):
            with self.subTest(screen=screen):
                self.assertIn('返回主菜单', tui.menu_text(screen))

    def test_once_status_shows_the_book_identity(self):
        code, out = _fixture.run_inproc(self.root, 'tui.py', '--once', 'status')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('测试之书', out)
        self.assertIn('chapters', out)

    def test_quit_with_zero(self):
        tui = _fixture.load_module(self.root, 'tui')
        import io
        from contextlib import redirect_stdout
        old = sys.stdin
        sys.stdin = io.StringIO('0\n')
        try:
            with redirect_stdout(io.StringIO()):
                code = tui.main([])
        finally:
            sys.stdin = old
        self.assertEqual(code, 0)

    def test_quit_with_q(self):
        tui = _fixture.load_module(self.root, 'tui')
        import io
        from contextlib import redirect_stdout
        old = sys.stdin
        sys.stdin = io.StringIO('q\n')
        try:
            with redirect_stdout(io.StringIO()):
                code = tui.main([])
        finally:
            sys.stdin = old
        self.assertEqual(code, 0)

    def test_ctrl_c_exits_cleanly(self):
        tui = _fixture.load_module(self.root, 'tui')
        import io
        from contextlib import redirect_stdout

        class Interrupting(io.StringIO):
            def readline(self, *args, **kwargs):
                raise KeyboardInterrupt

        old = sys.stdin
        sys.stdin = Interrupting()
        try:
            with redirect_stdout(io.StringIO()):
                code = tui.main([])
        finally:
            sys.stdin = old
        self.assertEqual(code, 0)

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
        self.assertIn('CLI 书名', self.read('data/config/book/book.toml'))

    def test_cli_settings_set_rejects_unknown_key(self):
        code, out = _fixture.run_inproc(self.root, 'cli.py', 'settings', 'set', 'nope', 'x')
        self.assertEqual(code, 2)
        self.assertIn('error', out)

if __name__ == '__main__':
    unittest.main()
