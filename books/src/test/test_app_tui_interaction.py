#!/usr/bin/env python3
"""Interactive menu: arrows navigate, one key runs, every run reports back."""

from __future__ import annotations

import importlib
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:app', 'tier:fast')

_fixture.ensure_tools_path()

class TuiInteractionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.tui = _fixture.load_module(self.root, 'tui')
        self.keys = importlib.import_module('app.keys')
        self.menu = importlib.import_module('core.menu')
        self.calls: list[str] = []

    def press(self, *keys: str, answers: list[str] | None = None):
        """Run the menu with scripted key presses, returning (code, output)."""
        queue = list(keys)

        def fake_read_key() -> str:
            return queue.pop(0) if queue else self.keys.KEY_ESC

        def fake_run(action: str):
            self.calls.append(action)
            return 0, f'输出-{action}-第一行\n输出-{action}-第二行'

        answers_list = list(answers or [])
        buffer = io.StringIO()
        with mock.patch.object(self.tui.keys, 'read_key', side_effect=fake_read_key), \
                mock.patch.object(self.tui.actions, 'run', side_effect=fake_run), \
                mock.patch.object(self.tui, 'confirm',
                                  side_effect=lambda *a, **k: bool(answers_list and answers_list.pop(0) == 'y')), \
                redirect_stdout(buffer):
            code = self.tui.main([])
        return code, buffer.getvalue()

    # -- two-level structure ---------------------------------------------
    def test_the_main_screen_offers_three_categories_and_exit(self):
        keys = [row[0] for row in self.tui.screen_rows('main')]
        self.assertEqual(keys, ['1', '2', '3', '0'])

    def test_enter_on_the_main_screen_opens_a_category_without_running(self):
        code, out = self.press(self.keys.KEY_ENTER, 'q')
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])
        self.assertIn('内容', out)

    def test_a_category_screen_carries_a_back_row(self):
        for screen in ('content', 'quality', 'config'):
            with self.subTest(screen=screen):
                keys = [row[0] for row in self.tui.screen_rows(screen)]
                self.assertEqual(keys[-1], '0')
                self.assertEqual(self.tui.screen_rows(screen)[-1][1], self.menu.BACK_ACTION)

    def test_zero_returns_to_the_previous_level_without_quitting(self):
        code, out = self.press('1', '0', 'q')
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])
        self.assertIn('主菜单', out)

    def test_zero_on_the_main_screen_quits(self):
        code, _out = self.press('0')
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])

    def test_escape_at_a_sub_level_goes_back_and_at_main_quits(self):
        code, out = self.press('2', self.keys.KEY_ESC, 'q')
        self.assertEqual(code, 0)
        self.assertIn('主菜单', out)

    def test_q_quits_from_a_sub_level(self):
        code, _out = self.press('1', 'q')
        self.assertEqual(code, 0)

    def test_the_cursor_starts_on_the_everyday_action(self):
        self.assertEqual(self.menu.default_cursor('content'),
                         self.menu.index_of('content', '2'))

    def test_enter_in_a_category_runs_its_default_entry(self):
        code, out = self.press('1', self.keys.KEY_ENTER, 'q')
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ['build'])
        self.assertIn('正在执行 手稿 → Markdown + HTML', out)

    def test_digit_key_runs_immediately_without_enter(self):
        self.press('2', '1')
        self.assertEqual(self.calls, ['check'])

    def test_l_shortcut_runs_the_llm_ingest(self):
        for pressed in ('l', 'L'):
            with self.subTest(key=pressed):
                self.calls.clear()
                self.press('1', pressed)
                self.assertEqual(self.calls, ['analyze-llm'])

    def test_arrows_move_within_a_screen_and_wrap(self):
        self.press('1', self.keys.KEY_UP, self.keys.KEY_ENTER)
        self.assertEqual(self.calls, ['analyze-llm'])

    # -- settings and provider priority -----------------------------------
    def settings_rows(self):
        return [{'key': 'dist', 'value': 'dist', 'kind': 'str', 'description': '产物目录'},
                {'key': 'llm.provider', 'value': 'main', 'kind': 'str', 'description': '默认 provider'}]

    def test_the_settings_screen_lists_writable_keys(self):
        with mock.patch.object(self.tui.settings, 'list_settings', self.settings_rows):
            rows = self.tui.screen_rows(self.menu.SETTINGS_SCREEN)
        self.assertEqual([row[0] for row in rows], ['1', '2', '0'])
        self.assertIn('dist', rows[0][2])

    def test_editing_a_setting_goes_through_the_settings_layer(self):
        edited = mock.Mock(return_value='out')
        with mock.patch.object(self.tui.settings, 'list_settings', self.settings_rows), \
                mock.patch.object(self.tui.settings, 'set_value', edited):
            status = self.tui.edit_setting('dist', reader=lambda _p: 'out')
        self.assertEqual(status, '已更新 dist = out')
        edited.assert_called_once_with('dist', 'out')

    def test_the_provider_screen_lists_the_fallback_order(self):
        order = [{'name': 'a', 'priority': 10}, {'name': 'b', 'priority': 20}]
        with mock.patch.object(self.tui.settings, 'provider_order', lambda: order):
            rows = self.tui.screen_rows(self.menu.PROVIDERS_SCREEN)
        self.assertEqual([row[0] for row in rows], ['1', '2', '0'])
        self.assertIn('a', rows[0][2])

    def test_moving_a_provider_up_or_down_uses_the_settings_layer(self):
        moved = mock.Mock(return_value='b, a')
        with mock.patch.object(self.tui.settings, 'move_provider', moved):
            up = self.tui.edit_provider('a', reader=lambda _p: 'u')
            cancel = self.tui.edit_provider('a', reader=lambda _p: '')
        self.assertIn('b, a', up)
        self.assertEqual(cancel, '未修改')
        moved.assert_called_once_with('a', -1)

    def test_c_opens_the_settings_screen(self):
        code, out = self.press('c', '0', 'q')
        self.assertEqual(code, 0)
        self.assertIn('配置项', out)

    # -- reporting --------------------------------------------------------
    def test_each_run_reports_timing_exit_code_and_output_tail(self):
        _code, out = self.press('2', '1')
        self.assertIn('输出-check-第二行', out)
        self.assertIn('退出码 0', out)
        self.assertIn('用时', out)
        self.assertIn('✓ 完成', out)

    def test_llm_entries_carry_a_badge_in_the_menu(self):
        text = self.tui.menu_text('content')
        llm_rows = [line for line in text.splitlines() if 'LLM' in line]
        self.assertTrue(llm_rows)

    def test_help_and_refresh_do_not_run_actions(self):
        _code, out = self.press('?', 'r', 'q')
        self.assertIn('两级菜单', out)
        self.assertIn('配置已重新读取', out)
        self.assertEqual(self.calls, [])

    def test_unknown_key_warns_and_menu_survives(self):
        _code, out = self.press('z', 'q')
        self.assertIn('无效按键', out)

    def test_deliver_asks_before_rebuilding(self):
        self.press('1', '3', answers=['n'])
        self.assertEqual(self.calls, [])
        _code, out = self.press('1', '3', answers=['n'])
        self.assertIn('已取消', out)

    def test_deliver_runs_when_confirmed(self):
        self.press('1', '3', answers=['y'])
        self.assertEqual(self.calls, ['deliver'])

if __name__ == '__main__':
    unittest.main()
