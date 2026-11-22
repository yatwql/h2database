#!/usr/bin/env python3
"""Interactive menu: arrows navigate, one key runs, every run reports back."""

from __future__ import annotations

import importlib
import io
import os
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
        self.kwargs: list[dict] = []

    def press(self, *keys: str, answers: list[str] | None = None):
        """Run the menu with scripted key presses, returning (code, output)."""
        queue = list(keys)

        def fake_read_key() -> str:
            return queue.pop(0) if queue else self.keys.KEY_ESC

        def fake_run(action: str, **kwargs):
            self.calls.append(action)
            self.kwargs.append(kwargs)
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
    def test_the_main_screen_carries_the_frequent_actions(self):
        keys = [row[0] for row in self.tui.screen_rows('main')]
        self.assertEqual(keys, ['1', '2', '3', '4', '5', '6', '7', '8', '0'])
        self.assertIn('@open:books', [row[1] for row in self.tui.screen_rows('main')])

    def test_the_main_screen_runs_actions_without_a_category(self):
        actions = [row[1] for row in self.tui.screen_rows('main')]
        self.assertIn('build', actions)
        self.assertIn('deliver', actions)

    def test_enter_on_the_main_screen_runs_the_everyday_action(self):
        code, out = self.press(self.keys.KEY_ENTER, 'q')
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ['build'])
        self.assertIn('主菜单', out)

    def test_a_category_screen_carries_a_back_row(self):
        for screen in ('quality', 'config'):
            with self.subTest(screen=screen):
                keys = [row[0] for row in self.tui.screen_rows(screen)]
                self.assertEqual(keys[-1], '0')
                self.assertEqual(self.tui.screen_rows(screen)[-1][1], self.menu.BACK_ACTION)

    def test_zero_returns_to_the_previous_level_without_quitting(self):
        code, out = self.press('4', '0', 'q')
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])
        self.assertIn('主菜单', out)

    def test_zero_on_the_main_screen_quits(self):
        code, _out = self.press('0')
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])

    def test_zero_collapses_a_finished_result_instead_of_quitting(self):
        code, out = self.press('3', '0', '3', 'q')
        self.assertEqual(code, 0)
        # the action ran twice: `0` returned to the menu, it did not exit
        self.assertEqual(self.calls, ['build', 'build'])
        self.assertIn('按任意键继续', out)

    def test_the_result_frame_does_not_show_an_input_prompt(self):
        _code, out = self.press('3', 'q')
        tail = [line for line in out.splitlines() if line.strip()][-3:]
        self.assertFalse(any(line.strip() == '❯' for line in tail), tail)

    def test_escape_at_a_sub_level_goes_back_and_at_main_quits(self):
        code, out = self.press('8', self.keys.KEY_ESC, 'q')
        self.assertEqual(code, 0)
        self.assertIn('主菜单', out)

    def test_q_quits_from_a_sub_level(self):
        code, _out = self.press('5', 'q')
        self.assertEqual(code, 0)

    def test_the_cursor_starts_on_the_everyday_action(self):
        self.assertEqual(self.menu.default_cursor('main'),
                         self.menu.index_of('main', '3'))

    def test_enter_inside_a_category_runs_its_default_entry(self):
        code, out = self.press('7', self.keys.KEY_ENTER, 'q')
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ['check'])
        self.assertIn('正在执行 全部质量门禁', out)

    def test_digit_key_runs_immediately_without_enter(self):
        self.press('7', '1')
        self.assertEqual(self.calls, ['check'])

    def test_the_config_screen_offers_the_fact_refresh(self):
        keys = [row[0] for row in self.tui.screen_rows('config')]
        self.assertEqual(keys, ['1', '2', '3', '4', '5', '6', '0'])
        self.press('8', '6')
        self.assertEqual(self.calls, ['analyze-refresh'])

    def test_the_llm_ingest_asks_before_overwriting_written_prose(self):
        self.press('l', answers=['n'])
        self.assertEqual(self.calls, ['analyze-llm'])
        self.assertFalse(self.kwargs[0].get('force'))

    def test_confirming_the_rewrite_passes_force(self):
        _code, out = self.press('l', answers=['y'])
        self.assertEqual(self.calls, ['analyze-llm'])
        self.assertTrue(self.kwargs[0].get('force'))
        self.assertIn('--force', out)

    def test_l_shortcut_runs_the_llm_ingest(self):
        for pressed in ('l', 'L'):
            with self.subTest(key=pressed):
                self.calls.clear()
                self.press(pressed)
                self.assertEqual(self.calls, ['analyze-llm'])

    def test_arrows_move_within_a_screen_and_wrap(self):
        # the cursor starts on "3 手稿 → Markdown + HTML"; up lands on analyze-llm
        self.press(self.keys.KEY_UP, self.keys.KEY_ENTER)
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
        _code, out = self.press('7', '1')
        self.assertIn('输出-check-第二行', out)
        self.assertIn('退出码 0', out)
        self.assertIn('用时', out)
        self.assertIn('✓ 完成', out)

    def test_llm_entries_carry_a_badge_in_the_menu(self):
        text = self.tui.menu_text('main')
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
        self.press('4', answers=['n'])
        self.assertEqual(self.calls, [])
        _code, out = self.press('4', answers=['n'])
        self.assertIn('已取消', out)

    def test_deliver_runs_when_confirmed(self):
        self.press('4', answers=['y'])
        self.assertEqual(self.calls, ['deliver'])

    def test_the_books_screen_lists_candidates_and_marks_the_active_one(self):
        rows = self.tui.screen_rows('books')
        self.assertEqual(rows[-1][1], '@back')
        self.assertTrue(rows[0][2].startswith('● '))
        self.assertTrue(rows[0][1].startswith('@book:'))

    def test_switching_books_rebinds_the_active_book(self):
        other = os.path.join(self.tmp.name, 'second-book')
        _fixture.build_book(other)
        # switch_book writes BOOK_ROOT for child processes; leaving it set would
        # point later suites at a temp directory this test deletes
        previous = os.environ.get('BOOK_ROOT')
        self.addCleanup(lambda: os.environ.__setitem__('BOOK_ROOT', previous)
                        if previous is not None
                        else os.environ.pop('BOOK_ROOT', None))
        message = self.tui.switch_book(other)
        self.assertIn('已切换', message)
        active = self.tui._config.current().root
        self.assertEqual(os.path.abspath(active), os.path.abspath(other))

    def test_switching_to_a_directory_without_a_book_is_refused(self):
        empty = os.path.join(self.tmp.name, 'empty')
        os.makedirs(empty, exist_ok=True)
        before = self.tui._config.current().root
        self.assertIn('没有找到 book.toml', self.tui.switch_book(empty))
        self.assertEqual(self.tui._config.current().root, before)

    def test_a_frame_is_cleared_before_it_is_drawn(self):
        class Tty(io.StringIO):
            def isatty(self) -> bool:
                return True

        buffer = Tty()
        with mock.patch.object(self.tui, 'USE_COLOR', True), \
                mock.patch.object(self.tui.sys, 'stdout', buffer):
            self.tui.clear_screen()
        self.assertTrue(buffer.getvalue().startswith('\033[H\033[2J'))

    def test_piped_output_stays_plain_text(self):
        buffer = io.StringIO()
        with mock.patch.object(self.tui, 'USE_COLOR', False), \
                mock.patch.object(self.tui.sys, 'stdout', buffer):
            self.tui.clear_screen()
        self.assertEqual(buffer.getvalue(), '')

    def test_the_menu_loop_clears_each_frame(self):
        class Tty(io.StringIO):
            def isatty(self) -> bool:
                return True

        buffer = Tty()
        with mock.patch.object(self.tui, 'USE_COLOR', True), \
                mock.patch.object(self.tui.sys, 'stdout', buffer), \
                mock.patch.object(self.tui.keys, 'read_key',
                                  side_effect=KeyboardInterrupt):
            self.tui.main([])
        self.assertIn('\033[H\033[2J', buffer.getvalue())

    def test_the_new_book_key_asks_for_a_name_and_a_source(self):
        answers = iter(['测试新书', ''])
        created = []
        target = os.path.join(self.tmp.name, 'created-book')
        with mock.patch('core.scaffold.create_book',
                        lambda name, source: (created.append((name, source))
                                              or (target, ['book.toml']))):
            message = self.tui.new_book(reader=lambda prompt='': next(answers))
        self.assertEqual(created, [('测试新书', '')])
        self.assertIn('已新建', message)

    def test_a_repository_source_is_cloned_into_the_new_book(self):
        answers = iter(['repo-book', 'https://github.com/a/b.git'])
        target = _fixture.build_book(os.path.join(self.tmp.name, 'repo-book'))
        cloned = []
        with mock.patch('core.scaffold.create_book',
                        lambda name, source: (target, ['book.toml'])), \
                mock.patch('core.fetch_source.main',
                           lambda argv: cloned.append(argv) or 0):
            message = self.tui.new_book(reader=lambda prompt='': next(answers))
        self.assertTrue(cloned)
        self.assertIn('克隆', message)

    def test_letter_shortcuts_alias_the_digits(self):
        self.assertEqual(self.tui.menu.resolve('main', 'A'), '1')
        self.assertEqual(self.tui.menu.resolve('main', 'l'), '2')
        self.assertEqual(self.tui.menu.resolve('main', 's'), '5')
        self.assertEqual(self.tui.menu.resolve('main', 'N'), '6')
        self.assertEqual(self.tui.menu.resolve('main', 't'), '7')
        self.assertEqual(self.tui.menu.resolve('main', 'c'), '8')
        self.assertEqual(self.tui.menu.resolve('config', 's'), 's')   # only main has letters

    def test_a_row_shows_its_letter_beside_the_digit(self):
        self.assertEqual(self.tui.menu.display_key('main', '1'), '1/A')
        self.assertEqual(self.tui.menu.display_key('main', '2'), '2/L')
        self.assertEqual(self.tui.menu.display_key('main', '6'), '6/N')
        self.assertEqual(self.tui.menu.display_key('main', '8'), '8/C')
        self.assertEqual(self.tui.menu.display_key('main', '0'), '0/Q')
        self.assertIn('2/L', [self.tui.menu.display_key('main', key)
                              for key in ('1', '2', '3', '4', '5', '6', '7', '8')])

    def test_the_letter_is_drawn_in_its_own_colour(self):
        with mock.patch.object(self.tui, 'USE_COLOR', True):
            rendered = self.tui._key('1/A', None, self.tui.PALETTE['shortcut'])
        self.assertIn(self.tui.PALETTE['shortcut'], rendered)
        self.assertIn('A', rendered)
        self.assertEqual(self.tui.menu.display_key('quality', '1'), '1')

    def test_pressing_a_letter_runs_the_same_action_as_its_digit(self):
        self.press('a')
        self.assertEqual(self.calls, ['analyze'])

if __name__ == '__main__':
    unittest.main()
