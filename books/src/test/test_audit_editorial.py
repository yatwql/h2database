#!/usr/bin/env python3
"""Tests for the editorial profile audit and its preset table.

The audit is a ratchet: the profile says which elements are required, the recorded
baseline says where the book stands today, and only a *drop* fails the build. Every case
here can fail — that is the point of the element — so the assertions name the exact count
or message rather than merely checking the exit code.
"""

import json
import unittest

from _cases import FixtureCase

TAGS = ("layer:audit", "tier:fast")


class EditorialProfileTest(FixtureCase):
    def test_an_unknown_profile_falls_back_loudly(self):
        self.append_book_toml('[editing.profile]\nname = "no-such-profile"\n')
        profile = self.module("_editorial").load_profile()
        self.assertEqual(profile["profile"], "manual")
        self.assertTrue(any("no-such-profile" in problem for problem in profile["problems"]))

    def test_an_unknown_element_is_reported_and_ignored(self):
        self.append_book_toml(
            '[editing.profile]\nname = "manual"\n\n[editing.elements.nonsense]\nenabled = true\n'
        )
        profile = self.module("_editorial").load_profile()
        self.assertIn("nonsense", " ".join(profile["problems"]))
        self.assertNotIn("nonsense", profile["rules"])

    def test_an_override_reaches_only_the_element_it_names(self):
        self.append_book_toml(
            '[editing.profile]\nname = "tutorial"\n\n[editing.elements.pitfalls]\nenabled = false\n'
        )
        rules = self.module("_editorial").load_profile()["rules"]
        self.assertFalse(rules["pitfalls"]["enabled"])
        self.assertTrue(rules["learning_goals"]["enabled"])

    def test_the_label_comes_from_the_book_then_the_language_pack(self):
        """Presets carry a section key; the wording is the manuscript language's."""
        editorial = self.module("_editorial")
        self.assertEqual(editorial.label({"heading": "章节要点"}), "章节要点")
        self.assertEqual(editorial.label({"section": "summary"}), "本章小结")
        # the fixture pack has `summary` but no `goals`, so the key is the fallback
        self.assertEqual(editorial.label({"section": "goals"}), "goals")
        self.assertEqual(editorial.label({}), "")

    def test_an_invalid_book_is_reported_when_the_table_is_read(self):
        """A broken `[editing]` table is a broken book: the config layer names the file."""
        self.append_book_toml("[editing.profile\nbroken\n")
        # the exception class is per module instance (the fixture reloads them), so the
        # contract asserted here is the message, not the identity of the class
        with self.assertRaises(Exception) as caught:
            self.module("_editorial").load_profile()
        self.assertIn("invalid TOML", str(caught.exception))


class EditorialCountingTest(FixtureCase):
    TEXT = (
        "# 第1章 测试章节\n\n"
        "## 1.1 学习目标\n\n- 目标一\n- 目标二\n- 目标三\n\n"
        "### 1.1.1 子节\n\n- 子条目不计入上层\n\n"
        "## 1.9 本章小结\n\n一段叙述，没有条目。\n\n"
        "| 甲 | 乙 |\n| --- | --- |\n| 1 | 2 |\n"
    )

    def test_items_are_counted_per_section_and_stop_at_the_next_heading(self):
        editorial = self.module("editorial")
        self.assertEqual(editorial.section_items(self.TEXT, "学习目标"), 3)
        self.assertEqual(editorial.section_items(self.TEXT, "本章小结"), 0)
        self.assertEqual(editorial.section_items(self.TEXT, "不存在的节"), 0)

    def test_table_density_counts_header_plus_separator_only(self):
        editorial = self.module("editorial")
        text = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
        self.assertEqual(editorial.table_count(text), 1)
        self.assertEqual(editorial.table_density(text), 333.33)

    def test_the_baseline_ratchet_fails_only_when_a_count_falls(self):
        editorial = self.module("editorial")
        metrics = {
            "rules": editorial._editorial.load_profile()["rules"],
            "files": [
                {
                    "file": "ch1-test.md",
                    "lines": 10,
                    "learning_goals": 2,
                    "key_points": 1,
                    "pitfalls": 1,
                    "tables": 1,
                    "table_density": 1.0,
                }
            ],
        }
        baseline = {"files": [dict(metrics["files"][0], learning_goals=3)]}
        problems = editorial.regressions(metrics, baseline)
        self.assertEqual(len(problems), 1)
        self.assertIn("fell from 3 to 2", problems[0])
        self.assertEqual(editorial.regressions(metrics, {"files": []}), [])

    def test_a_shortfall_is_recorded_then_tolerated_then_failed_once_it_drops(self):
        editorial = self.module("editorial")
        code = editorial.main([])
        self.assertEqual(code, 1)  # no baseline yet: a shortfall is unconcealed
        code = editorial.main(["--update-baseline"])
        self.assertEqual(code, 0)
        with open(editorial.baseline_path(), encoding="utf-8") as fh:
            self.assertIn("files", json.load(fh))
        self.assertEqual(editorial.main([]), 0)  # recorded shortfall is tolerated

    def test_learning_goals_are_counted_from_their_blockquote_block(self):
        """This book keeps them as `> - …` under the lead, not as a heading section."""
        editorial = self.module("editorial")
        text = ("> **本章导读**: 一句。\n> **章节要点**:\n"
                "> - 目标一\n> - 目标二\n> - 目标三\n\n正文。\n")
        self.assertEqual(editorial.blockquote_items(text, "章节要点"), 3)
        self.assertEqual(editorial.blockquote_items(text, "学习目标"), 0)


if __name__ == "__main__":
    unittest.main()
