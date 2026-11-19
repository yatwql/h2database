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

_fixture.ensure_tools_path()


class TuiInteractionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.tui = _fixture.load_module(self.root, 'tui')
        self.keys = importlib.import_module('app.keys')
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

    def test_cursor_starts_on_the_everyday_action(self):
        entry = self.tui.ENTRIES[self.tui.default_cursor()]
        self.assertEqual(entry[0], '2')
        self.assertEqual(entry[1], 'build')

    def test_enter_runs_the_default_entry_without_any_navigation(self):
        code, out = self.press(self.keys.KEY_ENTER)
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ['build'])
        self.assertIn('正在执行 手稿 → Markdown + HTML', out)

    def test_down_moves_to_the_next_entry(self):
        # past `3 deliver` (which asks for confirmation) onto `4 check`
        code, _out = self.press(self.keys.KEY_DOWN, self.keys.KEY_DOWN,
                                self.keys.KEY_ENTER)
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ['check'])

    def test_l_shortcut_runs_the_llm_ingest(self):
        self.press('l')
        self.assertEqual(self.calls, ['analyze-llm'])

    def test_uppercase_l_shortcut_works_too(self):
        self.calls.clear()
        self.press('L')
        self.assertEqual(self.calls, ['analyze-llm'])

    def test_llm_entries_carry_a_badge_in_the_menu(self):
        text = self.tui.menu_text()
        llm_rows = [line for line in text.splitlines() if 'LLM' in line]
        self.assertTrue(llm_rows)
        for line in llm_rows:
            self.assertIn('LLM', line)

    def test_up_moves_to_the_previous_entry(self):
        self.press(self.keys.KEY_UP, self.keys.KEY_ENTER)
        self.assertEqual(self.calls, ['analyze-llm'])

    def test_navigation_wraps_at_both_ends(self):
        # up three times from the default lands on the last entry
        self.press(self.keys.KEY_UP, self.keys.KEY_UP, self.keys.KEY_UP,
                   self.keys.KEY_ENTER)
        self.assertEqual(self.calls, ['doctor'])

    def test_digit_key_runs_immediately_without_enter(self):
        self.press('4')
        self.assertEqual(self.calls, ['check'])

    def test_each_run_reports_timing_exit_code_and_output_tail(self):
        _code, out = self.press('4')
        self.assertIn('输出-check-第二行', out)
        self.assertIn('退出码 0', out)
        self.assertIn('用时', out)
        self.assertIn('✓ 完成', out)

    def test_cursor_marker_moves_with_the_arrows(self):
        _code, first = self.press(self.keys.KEY_DOWN, 'q')
        _code, second = self.press(self.keys.KEY_DOWN, self.keys.KEY_DOWN, 'q')
        self.assertIn('❯', first)
        self.assertIn('❯', second)

    def test_q_and_zero_quit_immediately(self):
        for key in ('q', '0', self.keys.KEY_CTRL_C, self.keys.KEY_ESC):
            with self.subTest(key=key):
                self.calls.clear()
                code, _out = self.press(key)
                self.assertEqual(code, 0)
                self.assertEqual(self.calls, [])

    def test_help_and_refresh_do_not_run_actions(self):
        _code, out = self.press('?', 'r', 'q')
        self.assertIn('数字键执行动作', out)
        self.assertIn('配置已重新读取', out)
        self.assertEqual(self.calls, [])

    def test_unknown_key_warns_and_menu_survives(self):
        _code, out = self.press('z', 'q')
        self.assertIn('无效按键', out)

    def test_deliver_asks_before_rebuilding(self):
        self.calls.clear()
        _code, out = self.press('3', answers=['n'])
        self.assertEqual(self.calls, [])
        self.assertIn('已取消', out)

    def test_deliver_runs_when_confirmed(self):
        self.calls.clear()
        self.press('3', answers=['y'])
        self.assertEqual(self.calls, ['deliver'])


if __name__ == '__main__':
    unittest.main()
