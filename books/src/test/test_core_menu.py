"""The menu model decides keys, screens and estimates; none of that needs a terminal.

Channels only render what this module decides, so a wrong alias or a stale estimate
should fail here rather than after someone has pressed the key.
"""

from __future__ import annotations

import unittest
from unittest import mock

import _fixture

TAGS = ("layer:core", "tier:fast")

_fixture.ensure_tools_path()

_menu = __import__("core.menu", fromlist=["estimate", "tail_of", "run_report"])
menu = _menu


class MedianTest(unittest.TestCase):
    def history(self, *runs):
        return mock.patch.object(menu._perfhistory, "history", return_value=list(runs))

    def test_no_history_is_zero(self):
        with self.history():
            self.assertEqual(menu._mode_median("p0"), 0.0)

    def test_only_the_requested_mode_counts(self):
        with self.history({"mode": "p0", "seconds": 10}, {"mode": "p1", "seconds": 99}):
            self.assertEqual(menu._mode_median("p0"), 10.0)

    def test_garbage_seconds_are_skipped(self):
        with self.history(
            {"mode": "p0", "seconds": "oops"},
            {"mode": "p0", "seconds": 4},
            {"mode": "p0", "seconds": None},
        ):
            self.assertEqual(menu._mode_median("p0"), 4.0)

    def test_the_median_is_the_middle_of_the_sorted_values(self):
        with self.history(*[{"mode": "p0", "seconds": value} for value in (30, 10, 20)]):
            self.assertEqual(menu._mode_median("p0"), 20.0)


class EstimateTest(unittest.TestCase):
    def test_a_known_action_falls_back_to_its_default_range(self):
        with mock.patch.object(menu, "_mode_median", return_value=0.0):
            low, high = menu.estimate("build")
        self.assertEqual((low, high), menu.ESTIMATES["build"])

    def test_history_narrows_the_range_around_the_median(self):
        with mock.patch.object(menu, "_mode_median", return_value=100.0):
            low, high = menu.estimate("deliver")
        self.assertEqual((low, high), (70, 160))

    def test_the_full_run_adds_the_print_edition_to_the_delivery_median(self):
        with mock.patch.object(menu, "_mode_median", return_value=100.0):
            low, high = menu.estimate("deliver-all")
        self.assertEqual((low, high), (130, 230))

    def test_an_unknown_action_has_no_estimate(self):
        with mock.patch.object(menu, "_mode_median", return_value=0.0):
            self.assertIsNone(menu.estimate("nope"))


class AliasesTest(unittest.TestCase):
    def test_letters_resolve_case_insensitively(self):
        self.assertEqual(menu.resolve("main", "A"), "1")
        self.assertEqual(menu.resolve("main", "b"), "7")

    def test_a_screen_without_letters_passes_the_key_through(self):
        self.assertEqual(menu.resolve("config", "s"), "s")

    def test_the_display_shows_the_letter_next_to_the_digit(self):
        self.assertEqual(menu.display_key("main", "1"), "1/A")
        self.assertEqual(menu.display_key("library", "2"), "2/N")

    def test_a_key_without_a_letter_is_printed_alone(self):
        self.assertEqual(menu.display_key("config", "4"), "4")

    def test_groups_exist_only_on_the_main_screen(self):
        self.assertTrue(menu.groups_for("main"))
        self.assertEqual(menu.groups_for("quality"), [])

    def test_the_parent_of_a_known_screen_is_declared(self):
        self.assertEqual(menu.parent_of("library"), "main")
        self.assertEqual(menu.parent_of("books"), "library")

    def test_an_undeclared_screen_falls_back_to_main(self):
        self.assertEqual(menu.parent_of("mystery"), "main")

    def test_an_unknown_screen_has_no_entries(self):
        self.assertEqual(menu.entries("mystery"), [])

    def test_the_cursor_defaults_to_the_first_row_when_none_is_declared(self):
        self.assertEqual(menu.default_cursor("mystery"), 0)

    def test_index_of_finds_a_key_or_reports_minus_one(self):
        self.assertGreaterEqual(menu.index_of("main", "3"), 0)
        self.assertEqual(menu.index_of("main", "z"), -1)

    def test_navigation_and_policy_predicates(self):
        self.assertEqual(menu.opens_screen(menu.OPEN_PREFIX + "quality"), "quality")
        self.assertIsNone(menu.opens_screen("build"))
        self.assertTrue(menu.needs_confirmation("deliver-all"))
        self.assertFalse(menu.needs_confirmation("build"))
        self.assertTrue(menu.is_llm("llm-ask"))
        self.assertFalse(menu.is_llm("build"))

    def test_an_outcome_cannot_be_edited_after_the_fact(self):
        import dataclasses

        outcome = menu.Outcome(
            action="build", label="构建", code=0, output_lines=0, tail="", elapsed=1.0
        )
        self.assertTrue(outcome.ok)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            outcome.code = 1

    def test_every_confirmed_action_says_what_it_rewrites(self):
        for action in menu.CONFIRM_ACTIONS:
            self.assertTrue(menu.artifacts(action), action)

    def test_an_action_that_writes_nothing_reports_nothing(self):
        self.assertEqual(menu.artifacts("check"), "")


class TailTest(unittest.TestCase):
    def test_empty_output_is_empty(self):
        self.assertEqual(menu.tail_of(""), "")

    def test_blank_lines_are_dropped(self):
        self.assertEqual(menu.tail_of("a\n\n  \nb"), "a\nb")

    def test_a_long_output_keeps_the_tail_and_says_how_much_was_cut(self):
        text = "\n".join(f"line {index}" for index in range(30))
        shown = menu.tail_of(text, limit=5)
        self.assertIn("前 25 行略", shown)
        self.assertTrue(shown.endswith("line 29"))


class RunReportTest(unittest.TestCase):
    def test_progress_is_forwarded_and_the_tail_is_kept(self):
        seen = {}

        def fake_run(action, **kwargs):
            seen["action"] = action
            seen["kwargs"] = kwargs
            return 0, "one\ntwo\n"

        with mock.patch("core.actions.run", side_effect=fake_run):
            outcome = menu.run_report("build", "构建", on_progress=print, force=True)
        self.assertEqual(outcome.action, "build")
        self.assertEqual(outcome.output_lines, 2)
        self.assertTrue(outcome.ok)
        self.assertEqual(seen["kwargs"].get("on_progress"), print)
        self.assertTrue(seen["kwargs"].get("force"))

    def test_a_report_without_a_progress_callback_passes_none_through(self):
        with mock.patch("core.actions.run", return_value=(0, "one\n")) as run:
            outcome = menu.run_report("check", "检查")
        self.assertNotIn("on_progress", run.call_args.kwargs)
        self.assertEqual(outcome.output_lines, 1)


if __name__ == "__main__":
    unittest.main()
