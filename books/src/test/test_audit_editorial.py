#!/usr/bin/env python3
"""Tests for the editorial profile audit and its preset table.

The audit is a ratchet: the profile says which elements are required, the recorded
baseline says where the book stands today, and only a *drop* fails the build. Every case
here can fail — that is the point of the element — so the assertions name the exact count
or message rather than merely checking the exit code.
"""

import io as io_mod
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

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


    def test_every_goals_block_in_a_multi_chapter_file_is_counted(self):
        """Chapter 2 has its own lead block; counting only the first would hide a deletion."""
        editorial = self.module("editorial")
        text = ("> **章节要点**:\n> - 一\n> - 二\n\n# 第2章 另一章\n\n"
                "> **章节要点**:\n> - 三\n> - 四\n> - 五\n")
        self.assertEqual(editorial.blockquote_items(text, "章节要点"), 5)

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
            "rules": {},
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
        """The ratchet, tested without a book: measure and the baseline path are stubbed."""
        editorial = self.module("editorial")
        rules = {"learning_goals": {"enabled": True, "min_items": 3},
                 "key_points": {"enabled": True, "min_items": 4},
                 "pitfalls": {"enabled": True, "min_items": 1},
                 "table_density": {"enabled": False, "min_per_1000_lines": 1.0}}
        metrics = {"profile": "tutorial", "rules": rules, "problems": [],
                   "files": [{"file": "ch1-test.md", "lines": 10, "learning_goals": 1,
                              "key_points": 5, "pitfalls": 1, "tables": 1,
                              "table_density": 1.0}]}
        baseline = os.path.join(self.tmp.name, "editorial.json")
        with (
            mock.patch.object(editorial, "measure", return_value=metrics),
            mock.patch.object(editorial, "baseline_path", return_value=baseline),
        ):
            self.assertEqual(editorial.main([]), 1)  # no baseline: the shortfall is loud
            self.assertEqual(editorial.main(["--update-baseline"]), 0)
            with open(baseline, encoding="utf-8") as fh:
                self.assertIn("files", json.load(fh))
            self.assertEqual(editorial.main([]), 0)  # recorded shortfall is tolerated

    def test_learning_goals_are_counted_from_their_blockquote_block(self):
        """This book keeps them as `> - …` under the lead, not as a heading section."""
        editorial = self.module("editorial")
        text = ("> **本章导读**: 一句。\n> **章节要点**:\n"
                "> - 目标一\n> - 目标二\n> - 目标三\n\n正文。\n")
        self.assertEqual(editorial.blockquote_items(text, "章节要点"), 3)
        self.assertEqual(editorial.blockquote_items(text, "学习目标"), 0)


    def test_a_disabled_element_is_reported_but_not_ratcheted(self):
        """`enabled = false` means the profile does not require it, so a fall is not a failure."""
        editorial = self.module("editorial")
        metrics = {"rules": {"table_density": {"enabled": False}},
                   "files": [{"file": "ch1-test.md", "tables": 1}]}
        self.assertEqual(editorial.regressions(metrics, {"files": [{"file": "ch1-test.md",
                                                                  "tables": 5}]}), [])
        metrics["rules"]["table_density"]["enabled"] = True
        self.assertEqual(len(editorial.regressions(
            metrics, {"files": [{"file": "ch1-test.md", "tables": 5}]})), 1)

    def test_measure_files_counts_a_file_under_given_rules(self):
        """Inputs, not ambient state: no active book is needed to count a file."""
        editorial = self.module("editorial")
        preset = self.module("_editorial").PRESETS["tutorial"]
        rules = {name: dict(rule) for name, rule in preset.items()}
        # headings instead of section keys: no language pack is read in this case
        rules["learning_goals"]["heading"] = "章节要点"
        rules["key_points"]["heading"] = "本章小结"
        rules["pitfalls"]["heading"] = "常见误区"
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# 第1章 测试章节\n\n> **章节要点**:\n> - 一\n> - 二\n> - 三\n\n"
                     "## 1.9 本章小结\n\n- 甲\n- 乙\n\n## 1.10 常见误区\n\n- 丙\n")
        rows = editorial.measure_files([path], rules)
        self.assertEqual(rows[0]["learning_goals"], 3)
        self.assertEqual(rows[0]["pitfalls"], 1)
        self.assertEqual(rows[0]["file"], "ch1-test.md")

    def test_render_prints_the_element_table(self):
        editorial = self.module("editorial")
        rules = self.module("_editorial").PRESETS["tutorial"]
        metrics = {"profile": "tutorial", "rules": rules, "problems": [],
                   "files": [{"file": "ch1-test.md", "lines": 10, "learning_goals": 3,
                              "key_points": 4, "pitfalls": 1, "tables": 1,
                              "table_density": 0.5}]}
        text = editorial.render(metrics)
        self.assertIn("编辑要素", text)
        self.assertIn("ch1-test.md", text)

    def test_shortfalls_names_each_enabled_element_below_its_floor(self):
        editorial = self.module("editorial")
        rules = {"learning_goals": {"enabled": True, "min_items": 3},
                 "key_points": {"enabled": False},
                 "pitfalls": {"enabled": True, "min_items": 2},
                 "table_density": {"enabled": True, "min_per_1000_lines": 5}}
        metrics = {"rules": rules,
                   "files": [{"file": "a.md", "learning_goals": 1, "key_points": 0,
                              "pitfalls": 1, "table_density": 0.5}]}
        problems = editorial.shortfalls(metrics)
        self.assertEqual(len(problems), 3)
        self.assertTrue(any("learning_goals has 1 of 3" in p for p in problems))
        self.assertTrue(any("pitfalls has 1 of 2" in p for p in problems))
        self.assertTrue(any("table_density 0.5 of 5" in p for p in problems))

    def test_a_baseline_that_cannot_be_written_is_a_clean_error(self):
        editorial = self.module("editorial")
        blocker = os.path.join(self.tmp.name, "a-file")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        metrics = {"profile": "tutorial", "rules": {}, "problems": [], "files": []}
        with (
            mock.patch.object(editorial, "baseline_path",
                              return_value=os.path.join(blocker, "nested", "b.json")),
            self.assertRaises(SystemExit),
        ):
            editorial.save_baseline(metrics)

    def test_main_prints_the_recorded_shortfall_and_the_rise(self):
        editorial = self.module("editorial")
        rules = {"learning_goals": {"enabled": True, "min_items": 3},
                 "key_points": {"enabled": True, "min_items": 1},
                 "pitfalls": {"enabled": True, "min_items": 1},
                 "table_density": {"enabled": False}}
        short = {"profile": "tutorial", "rules": rules, "problems": [],
                 "files": [{"file": "a.md", "lines": 10, "learning_goals": 1,
                            "key_points": 2, "pitfalls": 2, "tables": 1,
                            "table_density": 1.0}]}
        grown = dict(short, files=[dict(short["files"][0], learning_goals=2)])
        baseline = os.path.join(self.tmp.name, "ed.json")
        with mock.patch.object(editorial, "baseline_path", return_value=baseline):
            with mock.patch.object(editorial, "measure", return_value=short):
                self.assertEqual(editorial.main([]), 1)   # no baseline: shortfall is loud
                editorial.main(["--update-baseline"])
                self.assertEqual(editorial.main([]), 0)   # recorded shortfall tolerated
            with mock.patch.object(editorial, "measure", return_value=grown):
                self.assertEqual(editorial.main([]), 0)   # a rise is allowed: it is a floor
            dropped = dict(short, files=[dict(short["files"][0], key_points=1)])
            with mock.patch.object(editorial, "measure", return_value=dropped):
                self.assertEqual(editorial.main([]), 1)   # a fall below the record fails

    def test_json_mode_answers_with_the_same_verdict(self):
        editorial = self.module("editorial")
        rules = {"learning_goals": {"enabled": True, "min_items": 3},
                 "key_points": {"enabled": True, "min_items": 1},
                 "pitfalls": {"enabled": True, "min_items": 1},
                 "table_density": {"enabled": False}}
        metrics = {"profile": "tutorial", "rules": rules, "problems": [],
                   "files": [{"file": "a.md", "lines": 10, "learning_goals": 1,
                              "key_points": 2, "pitfalls": 2, "tables": 1,
                              "table_density": 1.0}]}
        baseline = os.path.join(self.tmp.name, "ed.json")
        buffer = io_mod.StringIO()
        with (
            mock.patch.object(editorial, "measure", return_value=metrics),
            mock.patch.object(editorial, "baseline_path", return_value=baseline),
            redirect_stdout(buffer),
        ):
            self.assertEqual(editorial.main(["--json"]), 1)
            payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["has_baseline"])
        self.assertEqual(len(payload["shortfalls"]), 1)

if __name__ == "__main__":
    unittest.main()
