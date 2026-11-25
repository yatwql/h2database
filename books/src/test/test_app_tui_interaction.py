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

TAGS = ("layer:app", "tier:fast")

_fixture.ensure_tools_path()


class Tty(io.StringIO):
    """A stdout substitute that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


class TuiInteractionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.tui = _fixture.load_module(self.root, "tui")
        self.keys = importlib.import_module("app.keys")
        self.menu = importlib.import_module("core.menu")
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
            return 0, f"输出-{action}-第一行\n输出-{action}-第二行"

        answers_list = list(answers or [])
        buffer = io.StringIO()
        with (
            mock.patch.object(self.tui.keys, "read_key", side_effect=fake_read_key),
            mock.patch.object(self.tui.actions, "run", side_effect=fake_run),
            mock.patch.object(
                self.tui,
                "confirm",
                side_effect=lambda *a, **k: bool(answers_list and answers_list.pop(0) == "y"),
            ),
            redirect_stdout(buffer),
        ):
            code = self.tui.main([])
        return code, buffer.getvalue()

    # -- two-level structure ---------------------------------------------
    def test_the_main_screen_carries_the_frequent_actions(self):
        keys = [row[0] for row in self.tui.screen_rows("main")]
        self.assertEqual(keys, ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"])
        actions = [row[1] for row in self.tui.screen_rows("main")]
        self.assertIn("deliver-all", actions)
        self.assertIn("@open:library", actions)

    def test_the_books_screen_is_reached_through_its_category(self):
        rows = self.tui.screen_rows("library")
        self.assertEqual([row[0] for row in rows], ["1", "2", "0"])
        self.assertIn("@open:books", [row[1] for row in rows])
        self.assertEqual(self.tui.menu.parent_of("books"), "library")

    def test_the_main_screen_runs_actions_without_a_category(self):
        actions = [row[1] for row in self.tui.screen_rows("main")]
        self.assertIn("build", actions)
        self.assertIn("deliver", actions)

    def test_enter_on_the_main_screen_runs_the_everyday_action(self):
        code, out = self.press(self.keys.KEY_ENTER, "q")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ["build"])
        self.assertIn("主菜单", out)

    def test_a_category_screen_carries_a_back_row(self):
        for screen in ("quality", "config"):
            with self.subTest(screen=screen):
                keys = [row[0] for row in self.tui.screen_rows(screen)]
                self.assertEqual(keys[-1], "0")
                self.assertEqual(self.tui.screen_rows(screen)[-1][1], self.menu.BACK_ACTION)

    def test_zero_returns_to_the_previous_level_without_quitting(self):
        code, out = self.press("4", "0", "q")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])
        self.assertIn("主菜单", out)

    def test_zero_on_the_main_screen_quits(self):
        code, _out = self.press("0")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])

    def test_any_key_collapses_a_finished_result_instead_of_quitting(self):
        code, out = self.press("3", "0", "3", "q")
        self.assertEqual(code, 0)
        # the action ran twice: the first key returned to the menu, it did not exit
        self.assertEqual(self.calls, ["build", "build"])
        self.assertIn("按任意键回到菜单", out)

    def test_a_digit_under_a_finished_result_only_returns_to_the_menu(self):
        code, out = self.press("3", "3", "q")
        self.assertEqual(code, 0)
        # `3` dismissed the result instead of starting a second build under it
        self.assertEqual(self.calls, ["build"])
        self.assertIn("按任意键回到菜单", out)

    def test_escape_under_a_finished_result_does_not_leave_the_screen(self):
        code, out = self.press("9", "1", self.keys.KEY_ESC, "0", "q")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ["check"])  # the second `0` left the category
        self.assertIn("质量", out)

    def test_the_main_screen_reads_as_three_groups(self):
        text = self.tui.menu_text("main")
        order = [name for name in ("源码成书", "书籍管理", "配置与管理") if name in text]
        self.assertEqual(order, ["源码成书", "书籍管理", "配置与管理"], text)
        self.assertLess(text.index("源码成书"), text.index("1/A"))
        self.assertLess(text.index("书籍管理"), text.index("7/B"))
        self.assertLess(text.index("配置与管理"), text.index("8/C"))

    def test_every_main_row_sits_inside_a_group_except_exit(self):
        groups = self.tui.menu.groups_for("main")
        grouped = {key for _title, keys in groups for key in keys}
        rows = {key for key, _action, _label in self.tui.screen_rows("main")}
        self.assertEqual(rows - grouped, {"0"})

    def test_a_sub_screen_has_no_group_headings(self):
        text = self.tui.menu_text("quality")
        for name in ("源码成书", "书籍管理", "配置与管理"):
            self.assertNotIn(name, text)

    def test_the_result_frame_does_not_show_an_input_prompt(self):
        _code, out = self.press("3", "q")
        tail = [line for line in out.splitlines() if line.strip()][-3:]
        self.assertFalse(any(line.strip() == "❯" for line in tail), tail)

    def test_escape_at_a_sub_level_goes_back_and_at_main_quits(self):
        code, out = self.press("8", self.keys.KEY_ESC, "q")
        self.assertEqual(code, 0)
        self.assertIn("主菜单", out)

    def test_q_quits_from_a_sub_level(self):
        code, _out = self.press("6", "q")
        self.assertEqual(code, 0)

    def test_the_cursor_starts_on_the_everyday_action(self):
        self.assertEqual(self.menu.default_cursor("main"), self.menu.index_of("main", "3"))

    def test_enter_inside_a_category_runs_its_default_entry(self):
        code, out = self.press("9", self.keys.KEY_ENTER, "q")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, ["check"])
        self.assertIn("正在执行 全部质量门禁", out)

    def test_digit_key_runs_immediately_without_enter(self):
        self.press("9", "1")
        self.assertEqual(self.calls, ["check"])

    def test_the_config_screen_offers_the_fact_refresh(self):
        keys = [row[0] for row in self.tui.screen_rows("config")]
        self.assertEqual(keys, ["1", "2", "3", "4", "5", "6", "0"])
        self.press("8", "6")
        self.assertEqual(self.calls, ["analyze-refresh"])

    def test_the_llm_ingest_asks_before_overwriting_written_prose(self):
        self.press("l", answers=["n"])
        self.assertEqual(self.calls, ["analyze-llm"])
        self.assertFalse(self.kwargs[0].get("force"))

    def test_confirming_the_rewrite_passes_force(self):
        _code, out = self.press("l", answers=["y"])
        self.assertEqual(self.calls, ["analyze-llm"])
        self.assertTrue(self.kwargs[0].get("force"))
        self.assertIn("--force", out)

    def test_l_shortcut_runs_the_llm_ingest(self):
        for pressed in ("l", "L"):
            with self.subTest(key=pressed):
                self.calls.clear()
                self.press(pressed)
                self.assertEqual(self.calls, ["analyze-llm"])

    def test_arrows_move_within_a_screen_and_wrap(self):
        # the cursor starts on "3 手稿 → Markdown + HTML"; up lands on analyze-llm
        self.press(self.keys.KEY_UP, self.keys.KEY_ENTER)
        self.assertEqual(self.calls, ["analyze-llm"])

    # -- settings and provider priority -----------------------------------
    def settings_rows(self):
        return [
            {"key": "dist", "value": "dist", "kind": "str", "description": "产物目录"},
            {"key": "llm.provider", "value": "main", "kind": "str", "description": "默认 provider"},
        ]

    def test_the_settings_screen_lists_writable_keys(self):
        with mock.patch.object(self.tui.settings, "list_settings", self.settings_rows):
            rows = self.tui.screen_rows(self.menu.SETTINGS_SCREEN)
        self.assertEqual([row[0] for row in rows], ["1", "2", "0"])
        self.assertIn("dist", rows[0][2])

    def test_editing_a_setting_goes_through_the_settings_layer(self):
        edited = mock.Mock(return_value="out")
        with (
            mock.patch.object(self.tui.settings, "list_settings", self.settings_rows),
            mock.patch.object(self.tui.settings, "set_value", edited),
        ):
            status = self.tui.edit_setting("dist", reader=lambda _p: "out")
        self.assertEqual(status, "已更新 dist = out")
        edited.assert_called_once_with("dist", "out")

    def test_the_provider_screen_lists_the_fallback_order(self):
        order = [{"name": "a", "priority": 10}, {"name": "b", "priority": 20}]
        with mock.patch.object(self.tui.settings, "provider_order", lambda: order):
            rows = self.tui.screen_rows(self.menu.PROVIDERS_SCREEN)
        self.assertEqual([row[0] for row in rows], ["1", "2", "0"])
        self.assertIn("a", rows[0][2])

    def test_moving_a_provider_up_or_down_uses_the_settings_layer(self):
        moved = mock.Mock(return_value="b, a")
        with mock.patch.object(self.tui.settings, "move_provider", moved):
            up = self.tui.edit_provider("a", reader=lambda _p: "u")
            cancel = self.tui.edit_provider("a", reader=lambda _p: "")
        self.assertIn("b, a", up)
        self.assertEqual(cancel, "未修改")
        moved.assert_called_once_with("a", -1)

    def test_c_opens_the_settings_screen(self):
        code, out = self.press("c", "0", "q")
        self.assertEqual(code, 0)
        self.assertIn("配置项", out)

    # -- reporting --------------------------------------------------------
    def test_each_run_reports_timing_exit_code_and_output_tail(self):
        _code, out = self.press("9", "1")
        self.assertIn("输出-check-第二行", out)
        self.assertIn("退出码 0", out)
        self.assertIn("用时", out)
        self.assertIn("✓ 完成", out)

    def test_llm_entries_carry_a_badge_in_the_menu(self):
        text = self.tui.menu_text("main")
        llm_rows = [line for line in text.splitlines() if "LLM" in line]
        self.assertTrue(llm_rows)

    def test_help_and_refresh_do_not_run_actions(self):
        _code, out = self.press("?", "r", "q")
        self.assertIn("两级菜单", out)
        self.assertIn("配置已重新读取", out)
        self.assertEqual(self.calls, [])

    def test_unknown_key_warns_and_menu_survives(self):
        _code, out = self.press("z", "q")
        self.assertIn("无效按键", out)

    def test_deliver_asks_before_rebuilding(self):
        self.press("4", answers=["n"])
        self.assertEqual(self.calls, [])
        _code, out = self.press("4", answers=["n"])
        self.assertIn("已取消", out)

    def test_deliver_runs_when_confirmed(self):
        self.press("4", answers=["y"])
        self.assertEqual(self.calls, ["deliver"])

    def test_the_books_screen_lists_candidates_and_marks_the_active_one(self):
        rows = self.tui.screen_rows("books")
        self.assertEqual(rows[-1][1], "@back")
        self.assertTrue(rows[0][2].startswith("● "))
        self.assertTrue(rows[0][1].startswith("@book:"))

    def test_switching_books_rebinds_the_active_book(self):
        other = os.path.join(self.tmp.name, "second-book")
        _fixture.build_book(other)
        # switch_book writes BOOK_ROOT for child processes; leaving it set would
        # point later suites at a temp directory this test deletes
        previous = os.environ.get("BOOK_ROOT")
        self.addCleanup(
            lambda: (
                os.environ.__setitem__("BOOK_ROOT", previous)
                if previous is not None
                else os.environ.pop("BOOK_ROOT", None)
            )
        )
        message = self.tui.switch_book(other)
        self.assertIn("已切换", message)
        active = self.tui._config.current().root
        self.assertEqual(os.path.abspath(active), os.path.abspath(other))

    def test_switching_to_a_directory_without_a_book_is_refused(self):
        empty = os.path.join(self.tmp.name, "empty")
        os.makedirs(empty, exist_ok=True)
        before = self.tui._config.current().root
        self.assertIn("没有找到 book.toml", self.tui.switch_book(empty))
        self.assertEqual(self.tui._config.current().root, before)

    def test_a_frame_is_cleared_before_it_is_drawn(self):
        buffer = Tty()
        with (
            mock.patch.object(self.tui, "USE_COLOR", True),
            mock.patch.object(self.tui.sys, "stdout", buffer),
        ):
            self.tui.clear_screen()
        self.assertTrue(buffer.getvalue().startswith("\033[H\033[2J"))

    def test_piped_output_stays_plain_text(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(self.tui, "USE_COLOR", False),
            mock.patch.object(self.tui.sys, "stdout", buffer),
        ):
            self.tui.clear_screen()
        self.assertEqual(buffer.getvalue(), "")

    def test_the_menu_loop_clears_each_frame(self):
        buffer = Tty()
        with (
            mock.patch.object(self.tui, "USE_COLOR", True),
            mock.patch.object(self.tui.sys, "stdout", buffer),
            mock.patch.object(self.tui.keys, "read_key", side_effect=KeyboardInterrupt),
        ):
            self.tui.main([])
        self.assertIn("\033[H\033[2J", buffer.getvalue())

    def test_the_new_book_key_asks_for_a_name_and_a_source(self):
        answers = iter(["测试新书", ""])
        created = []
        target = os.path.join(self.tmp.name, "created-book")
        with mock.patch(
            "core.scaffold.create_book",
            lambda name, source: created.append((name, source)) or (target, ["book.toml"]),
        ):
            message = self.tui.new_book(reader=lambda prompt="": next(answers))
        self.assertEqual(created, [("测试新书", "")])
        self.assertIn("已新建", message)

    def test_a_repository_source_is_cloned_into_the_new_book(self):
        answers = iter(["repo-book", "https://github.com/a/b.git"])
        target = _fixture.build_book(os.path.join(self.tmp.name, "repo-book"))
        cloned = []
        with (
            mock.patch("core.scaffold.create_book", lambda name, source: (target, ["book.toml"])),
            mock.patch("core.fetch_source.main", lambda argv: cloned.append(argv) or 0),
        ):
            message = self.tui.new_book(reader=lambda prompt="": next(answers))
        self.assertTrue(cloned)
        self.assertIn("克隆", message)

    def test_letter_shortcuts_alias_the_digits(self):
        self.assertEqual(self.tui.menu.resolve("main", "A"), "1")
        self.assertEqual(self.tui.menu.resolve("main", "l"), "2")
        self.assertEqual(self.tui.menu.resolve("main", "m"), "3")
        self.assertEqual(self.tui.menu.resolve("main", "F"), "6")
        self.assertEqual(self.tui.menu.resolve("main", "B"), "7")
        self.assertEqual(self.tui.menu.resolve("main", "c"), "8")
        self.assertEqual(self.tui.menu.resolve("main", "t"), "9")
        self.assertEqual(self.tui.menu.resolve("library", "s"), "1")
        self.assertEqual(self.tui.menu.resolve("library", "N"), "2")
        self.assertEqual(
            self.tui.menu.resolve("config", "s"), "s"
        )  # only main/library have letters

    def test_a_row_shows_its_letter_beside_the_digit(self):
        self.assertEqual(self.tui.menu.display_key("main", "1"), "1/A")
        self.assertEqual(self.tui.menu.display_key("main", "2"), "2/L")
        self.assertEqual(self.tui.menu.display_key("main", "3"), "3/M")
        self.assertEqual(self.tui.menu.display_key("main", "6"), "6/F")
        self.assertEqual(self.tui.menu.display_key("main", "7"), "7/B")
        self.assertEqual(self.tui.menu.display_key("main", "4"), "4/E")
        self.assertEqual(self.tui.menu.display_key("main", "5"), "5/P")
        self.assertEqual(self.tui.menu.display_key("main", "8"), "8/C")
        self.assertEqual(self.tui.menu.display_key("main", "9"), "9/T")
        self.assertEqual(self.tui.menu.display_key("library", "1"), "1/S")
        self.assertEqual(self.tui.menu.display_key("library", "2"), "2/N")
        self.assertEqual(self.tui.menu.display_key("main", "0"), "0/Q")
        self.assertIn(
            "2/L",
            [
                self.tui.menu.display_key("main", key)
                for key in ("1", "2", "3", "4", "5", "6", "7", "8", "9")
            ],
        )

    def test_the_letter_is_drawn_in_its_own_colour(self):
        with mock.patch.object(self.tui, "USE_COLOR", True):
            rendered = self.tui._key("1/A", None, self.tui.PALETTE["shortcut"])
        self.assertIn(self.tui.PALETTE["shortcut"], rendered)
        self.assertIn("A", rendered)
        self.assertEqual(self.tui.menu.display_key("quality", "1"), "1")

    def test_pressing_a_letter_runs_the_same_action_as_its_digit(self):
        self.press("a")
        self.assertEqual(self.calls, ["analyze"])

    def test_the_confirmation_says_which_artifacts_will_be_rewritten(self):
        asked: list[str] = []

        def fake_confirm(question, reader=None):
            asked.append(question)
            return False

        with (
            mock.patch.object(self.tui, "confirm", side_effect=fake_confirm),
            redirect_stdout(io.StringIO()),
        ):
            text = self.tui.run_entry("deliver-all", "手稿 → 全量交付")
        self.assertEqual(len(asked), 1)
        self.assertIn("Markdown", asked[0])
        self.assertIn("印刷版 PDF", asked[0])
        self.assertIn("覆盖", asked[0])
        self.assertIn("未改动", text)

    def test_the_progress_and_outcome_name_the_artifacts(self):
        outcome = self.menu.Outcome(
            action="build", label="构建", code=0, output_lines=1, tail="done", elapsed=1.0
        )
        buffer = io.StringIO()
        with (
            mock.patch.object(self.tui.menu, "run_report", return_value=outcome),
            redirect_stdout(buffer),
        ):
            text = self.tui.run_entry("build", "手稿 → Markdown + HTML")
        self.assertIn("正在重建 合并 Markdown 与 HTML", buffer.getvalue())
        self.assertIn("已重建：合并 Markdown 与 HTML", text)

    def test_a_failed_run_says_the_artifacts_were_not_updated(self):
        outcome = self.menu.Outcome(
            action="deliver", label="交付", code=1, output_lines=1, tail="step failed", elapsed=1.0
        )
        buffer = io.StringIO()
        with (
            mock.patch.object(self.tui.menu, "run_report", return_value=outcome),
            mock.patch.object(self.tui, "confirm", return_value=True),
            redirect_stdout(buffer),
        ):
            text = self.tui.run_entry("deliver", "EPUB + PDF")
        self.assertIn("未更新", text)

    def test_the_estimate_is_a_short_range_not_a_guess(self):
        # measured: build ~0.3 s, deliver ~92 s, print ~43 s, all-in ~135 s
        self.assertLessEqual(menu_estimate("build")[1], 30)
        self.assertLessEqual(menu_estimate("print")[1], 120)
        self.assertLessEqual(menu_estimate("deliver-all")[1], 300)
        for action in ("build", "deliver", "print", "deliver-all"):
            low, high = menu_estimate(action)
            self.assertLess(low, high)

    def test_the_outcome_compares_the_actual_time_with_the_estimate(self):
        outcome = self.menu.Outcome(
            action="print", label="印刷版", code=0, output_lines=1, tail="done", elapsed=43.0
        )
        buffer = io.StringIO()
        with (
            mock.patch.object(self.tui.menu, "run_report", return_value=outcome),
            mock.patch.object(self.tui, "confirm", return_value=True),
            redirect_stdout(buffer),
        ):
            text = self.tui.run_entry("print", "印刷版 PDF")
        self.assertIn("用时 0:43", text)
        self.assertIn("预计", text)

    def test_a_run_without_an_estimate_reports_only_the_elapsed_time(self):
        outcome = self.menu.Outcome(
            action="check", label="门禁", code=0, output_lines=1, tail="done", elapsed=2.0
        )
        buffer = io.StringIO()
        with (
            mock.patch.object(self.tui.menu, "run_report", return_value=outcome),
            mock.patch.object(self.tui.menu, "estimate", return_value=None),
            redirect_stdout(buffer),
        ):
            text = self.tui.run_entry("check", "全部门禁")
        self.assertNotIn("预计", buffer.getvalue())
        self.assertNotIn("预计", text)
        self.assertIn("用时 0:02", text)

    def test_the_settings_entry_opens_the_configuration_editor(self):
        with mock.patch.object(self.tui, "configure", return_value="配置页"):
            self.assertEqual(self.tui.run_entry("settings", "配置"), "配置页")

    def test_once_settings_prints_the_editor_to_stdout(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(self.tui, "configure", return_value="配置页\n"),
            redirect_stdout(buffer),
        ):
            code = self.tui.main(["--once", "settings"])
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue(), "配置页\n")

    def test_a_group_whose_rows_are_gone_renders_nothing_for_it(self):
        with mock.patch.object(self.menu, "MENU_GROUPS", (("已消失的分组", ("nonexistent",)),)):
            text = self.tui.menu_text("main")
        self.assertNotIn("已消失的分组", text)
        self.assertIn("源码 → 手稿", text)

    def test_the_quit_row_exits_through_the_handler(self):
        # the cursor starts on the everyday row (index 2); seven downs reach 退出
        presses = (self.keys.KEY_DOWN,) * 7 + (self.keys.KEY_ENTER,)
        code, out = self.press(*presses)
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])
        self.assertTrue(out.endswith("\n"), out[-40:])


def menu_estimate(action: str) -> tuple[int, int]:
    """The estimate as the menu module computes it (no book needed for defaults)."""
    module = importlib.import_module("core.menu")
    return module.estimate(action) or (0, 0)


class EditSettingTest(unittest.TestCase):
    """The settings prompt refuses anything it cannot apply, without raising."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.tui = _fixture.load_module(self.root, "tui")

    def answer(self, *replies: str):
        queue = list(replies)
        return lambda _prompt="": queue.pop(0) if queue else ""

    def settings_row(self):
        return [{"key": "k", "value": "v", "description": "说明"}]

    def test_a_non_numeric_choice_changes_nothing(self):
        with (
            mock.patch.object(self.tui.settings, "list_settings", return_value=self.settings_row()),
            redirect_stdout(io.StringIO()),
        ):
            text = self.tui.configure(reader=self.answer("abc"))
        self.assertEqual(text, "未修改")

    def test_an_out_of_range_choice_changes_nothing(self):
        with (
            mock.patch.object(self.tui.settings, "list_settings", return_value=self.settings_row()),
            redirect_stdout(io.StringIO()),
        ):
            text = self.tui.configure(reader=self.answer("99"))
        self.assertEqual(text, "未修改")

    def test_an_empty_value_changes_nothing(self):
        with mock.patch.object(
            self.tui.settings, "list_settings", return_value=self.settings_row()
        ):
            text = self.tui.edit_setting("k", reader=self.answer(""))
        self.assertEqual(text, "未修改")

    def test_a_rejected_value_is_reported_as_a_failure(self):
        with (
            mock.patch.object(
                self.tui.settings, "list_settings", return_value=[{"key": "k", "value": "v"}]
            ),
            mock.patch.object(
                self.tui.settings, "set_value", side_effect=ValueError("not allowed")
            ),
        ):
            text = self.tui.edit_setting("k", reader=self.answer("new"))
        self.assertIn("修改失败", text)

    def test_a_rejected_provider_move_is_reported_as_a_failure(self):
        with mock.patch.object(self.tui.settings, "move_provider", side_effect=KeyError("a")):
            text = self.tui.edit_provider("a", reader=self.answer("u"))
        self.assertIn("修改失败", text)

        with (
            mock.patch.object(
                self.tui.settings, "list_settings", return_value=[{"key": "k", "value": "v"}]
            ),
            mock.patch.object(self.tui.settings, "set_value", return_value="nv"),
        ):
            text = self.tui.edit_setting("k", reader=self.answer("new"))
        self.assertIn("已更新 k = nv", text)


class ProgressLinesTest(unittest.TestCase):
    """Progress lines drop repeats and keep the stamp; a joined line is unwrapped."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.tui = _fixture.load_module(self.root, "tui")

    def outcome(self):
        return self.tui.menu.Outcome(
            action="build", label="构建", code=0, output_lines=1, tail="", elapsed=1.0
        )

    def run_with(self, lines: list[str]):
        def fake(action, label, force=False, on_progress=None):
            progress = on_progress or (lambda _line: None)
            for line in lines:
                progress(line)
            return self.outcome()

        buffer = io.StringIO()
        with (
            mock.patch.object(self.tui.menu, "run_report", side_effect=fake),
            redirect_stdout(buffer),
        ):
            self.tui._run_with_progress("build", "构建", False)
        return buffer.getvalue()

    def test_a_repeated_stage_is_printed_once(self):
        out = self.run_with(
            ["2026-01-01 00:00:00 INFO x 阶段一", "2026-01-01 00:00:01 INFO x 阶段一"]
        )
        self.assertEqual(out.count("阶段一"), 1)

    def test_a_blank_line_is_ignored(self):
        out = self.run_with(["   ", "阶段二"])
        self.assertEqual(out.strip().count("阶段二"), 1)

    def test_a_log_line_loses_its_timestamp(self):
        out = self.run_with(["2026-01-01 00:00:00 INFO x 阶段三"])
        self.assertNotIn("2026-01-01", out)
        self.assertIn("阶段三", out)


if __name__ == "__main__":
    unittest.main()


class SettingEditAndConfirmTest(unittest.TestCase):
    """The two prompts that take a keypress: editing a setting and confirming."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.tui = _fixture.load_module(self.root, "tui")

    def reader(self, *answers: str):
        remaining = list(answers)
        return lambda _prompt="": remaining.pop(0) if remaining else ""

    def rows(self) -> list[dict]:
        return [{"key": "book.title", "value": "旧名", "description": "书名"}]

    def test_an_empty_answer_leaves_the_setting_alone(self):
        with (
            mock.patch.object(self.tui.settings, "list_settings", self.rows),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(self.tui.configure(self.reader("1", "")), "未修改")

    def test_a_changed_value_is_stored_and_reported(self):
        with (
            mock.patch.object(self.tui.settings, "list_settings", self.rows),
            mock.patch.object(self.tui.settings, "set_value", return_value="新名"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(
                self.tui.configure(self.reader("1", "新名")), "已更新 book.title = 新名"
            )

    def test_a_rejected_value_is_reported_instead_of_crashing(self):
        with (
            mock.patch.object(self.tui.settings, "list_settings", self.rows),
            mock.patch.object(self.tui.settings, "set_value", side_effect=ValueError("bad")),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(self.tui.configure(self.reader("1", "x")), "修改失败：bad")

    def test_confirm_accepts_y_and_yes_and_chinese_yes(self):
        for answer in ("y", "YES", "是"):
            with self.subTest(answer=answer):
                self.assertTrue(self.tui.confirm("继续？", self.reader(answer)))

    def test_confirm_defaults_to_no(self):
        self.assertFalse(self.tui.confirm("继续？", self.reader("")))
        self.assertFalse(self.tui.confirm("继续？", self.reader("n")))


class HandleDispatchAndNewBookTest(unittest.TestCase):
    """Every menu action reaches its own handler, and a failed create is reported."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.tui = _fixture.load_module(self.root, "tui")
        self.menu = importlib.import_module("core.menu")

    def test_quit_and_back_answer_their_own_exits(self):
        self.assertEqual(self.tui.handle(self.menu.QUIT_ACTION, "退出", "main"), (True, "main", ""))
        quit_now, screen, said = self.tui.handle(self.menu.BACK_ACTION, "返回", "quality")
        self.assertFalse(quit_now)
        self.assertEqual((screen, said), (self.menu.parent_of("quality"), ""))

    def test_a_screen_action_switches_without_a_status_line(self):
        action = self.menu.OPEN_PREFIX + "quality"
        self.assertEqual(self.tui.handle(action, "质量", "main"), (False, "quality", ""))

    def test_each_prefixed_action_reaches_its_handler(self):
        with (
            mock.patch.object(self.tui, "edit_setting", return_value="set"),
            mock.patch.object(self.tui, "edit_provider", return_value="move"),
            mock.patch.object(self.tui, "new_book", return_value="new"),
            mock.patch.object(self.tui, "switch_book", return_value="switch"),
        ):
            cases = {
                "@set:print_scale": "set",
                "@move:openai": "move",
                self.menu.NEW_BOOK_ACTION: "new",
                self.menu.BOOK_ACTION_PREFIX + "other-book": "switch",
            }
            for action, expected in cases.items():
                with self.subTest(action=action):
                    quit_now, screen, status = self.tui.handle(action, "x", "main")
                    self.assertFalse(quit_now)
                    self.assertEqual((screen, status), ("main", expected))

    def test_an_empty_book_name_cancels_without_creating_anything(self):
        with mock.patch("core.scaffold.create_book") as create:
            said = self.tui.new_book(lambda _prompt="": "")
        create.assert_not_called()
        self.assertIn("书名不能为空", said)

    def test_a_failed_create_is_reported_instead_of_raising(self):
        with mock.patch("core.scaffold.create_book", side_effect=OSError("denied")):
            said = self.tui.new_book(lambda _prompt="": "demo" if "书名" in _prompt else "")
        self.assertIn("新建失败", said)
        self.assertIn("denied", said)
