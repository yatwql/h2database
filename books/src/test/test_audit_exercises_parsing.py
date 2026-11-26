#!/usr/bin/env python3
"""Exercises gate: chapter-slot parsing and the per-file audit."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class SlotParsingTest(unittest.TestCase):
    def setUp(self):
        self.mod = _fixture.load_module(BOOK_ROOT, "exercises")

    def lines(self, text: str) -> list[str]:
        return text.splitlines(keepends=True)

    def test_a_complete_slot_is_found(self):
        text = (
            "# 第1章 测试\n\n## 1.9 本章小结\n\n小结。\n\n"
            "## 1.10 延伸思考\n\n1. 练习\n\n## 1.11 延展阅读\n\n- 参考\n"
        )
        slots = self.mod.parse_chapter_slots(self.lines(text))
        self.assertTrue(slots)
        self.assertEqual(slots[0]["chapter"], 1)

    def test_a_file_starting_mid_chapter_uses_the_h2_number(self):
        text = "## 6.5 本章小结\n\n小结。\n\n## 6.6 延伸思考\n\n1. 练习\n"
        slots = self.mod.parse_chapter_slots(self.lines(text))
        self.assertTrue(slots)
        self.assertEqual(slots[0]["chapter"], 6)

    def test_exercises_without_a_chapter_heading_are_attributed(self):
        text = "## 3.7 延伸思考\n\n1. 练习\n\n## 3.8 延展阅读\n\n- 参考\n"
        slots = self.mod.parse_chapter_slots(self.lines(text))
        self.assertEqual(slots[0]["chapter"], 3)

    def test_fenced_blocks_are_ignored(self):
        text = "# 第1章 测试\n\n## 1.9 本章小结\n\n小结。\n\n```text\n## 1.10 延伸思考\n```\n"
        slots = self.mod.parse_chapter_slots(self.lines(text))
        self.assertTrue(all(slot["chapter"] == 1 for slot in slots))

    def test_section_end_stops_at_the_next_heading(self):
        text = self.lines("## 1.9 延伸思考\n\n1. 练习\n\n## 1.10 延展阅读\n\n- 参考\n")
        end = self.mod.find_section_end(text, 0)
        self.assertGreaterEqual(end, 1)


class AuditFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "exercises")

    def write(self, text: str) -> str:
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_audit_file_counts_the_exercises(self):
        path = self.write(
            "# 第1章 测试\n\n## 1.9 本章小结\n\n小结。\n\n"
            "## 1.10 延伸思考\n\n"
            "**1. 🟢★ 练习一**\n\n> 提示：看 §1.1\n> 回顾：§1.1 小节\n\n"
            "**2. 🔵★★ 练习二**\n\n> 提示：看 §1.1\n> 回顾：§1.1 小节\n\n"
            "## 1.11 延展阅读\n\n- 参考\n"
        )
        report = self.mod.audit_file(path)
        self.assertIn("slots", report)
        slot = report["slots"][0]
        self.assertEqual(slot["exercise_count"], 2)
        self.assertTrue(slot["placement_ok"])

    def test_audit_file_reports_a_missing_slot_instead_of_crashing(self):
        path = self.write("# 第1章 测试\n\n没有小结也没有练习。\n")
        report = self.mod.audit_file(path)
        self.assertEqual(len(report["slots"]), 1)
        self.assertFalse(report["slots"][0]["has_exercises"])
        self.assertEqual(report["issues"], ["ch1 缺少 ## N.X 延伸思考 小节"])




class ExerciseIssueBranchesTest(unittest.TestCase):
    """Each missing marker becomes its own issue line, and a full chapter passes."""

    def setUp(self):
        self.mod = _fixture.load_module(BOOK_ROOT, "exercises")

    def lines(self, text: str) -> list[str]:
        return text.splitlines(keepends=True)

    def slot(self, text: str) -> dict:
        slot = self.mod.parse_chapter_slots(self.lines(text))[0]
        issues: list[str] = []
        report = self.mod._slot_exercises(self.lines(text), slot, issues)
        return {"report": report, "issues": issues}

    CHAPTER = (
        "# 第1章 测试\n\n## 1.9 本章小结\n\n小结。\n\n"
        "## 1.10 延伸思考\n\n"
        "**1. 🟢★ 说说你的看法**\n\n{hint}{review}\n"
        "## 1.11 延展阅读\n\n- 参考\n"
    )
    HINT = "> 提示：先看写入路径。\n\n"
    REVIEW = "> 回顾：见 §1.2 的顺序。\n"

    def text(self, hint: str, review: str) -> str:
        return self.CHAPTER.replace("{hint}", hint).replace("{review}", review)

    def test_a_complete_chapter_has_no_issues(self):
        outcome = self.slot(self.text(self.HINT, self.REVIEW))
        self.assertEqual(outcome["issues"], [])
        self.assertTrue(outcome["report"]["all_have_hint"])

    def test_a_missing_hint_line_is_reported(self):
        outcome = self.slot(self.text("", self.REVIEW))
        self.assertTrue(any("缺少 提示 行" in issue for issue in outcome["issues"]))
        self.assertFalse(outcome["report"]["all_have_hint"])

    def test_a_missing_review_line_is_reported(self):
        outcome = self.slot(self.text(self.HINT, ""))
        self.assertTrue(any("缺少 回顾 行" in issue for issue in outcome["issues"]))
        self.assertFalse(outcome["report"]["all_have_review"])

    def test_a_review_without_an_anchor_is_reported(self):
        outcome = self.slot(self.text(self.HINT, "> 回顾：没有坐标。\n"))
        self.assertTrue(any("无 §X.Y 锚点" in issue for issue in outcome["issues"]))
        self.assertFalse(outcome["report"]["all_anchors_present"])

    def test_a_chapter_that_meets_the_floor_passes_the_report(self):
        report = {
            "file": "ch1.md",
            "issues": [],
            "slots": [
                {
                    "chapter": 1,
                    "exercise_count": self.mod.PER_CHAPTER_FLOOR,
                    "placement_ok": True,
                    "all_have_hint": True,
                    "all_have_review": True,
                    "all_anchors_present": True,
                    "difficulties": [1, 2, 3],
                    "emoji_distribution": {"🟢": 1, "🔵": 1, "🟠": 1},
                }
            ],
        }
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.render_report([report], total_floor=1)
        self.assertEqual(code, 0)
        self.assertIn("章节合格：1 / 1", buffer.getvalue())


class ExerciseCliModesTest(unittest.TestCase):
    """`--template` prints the template, `--target` scans one file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "exercises")

    def test_the_template_mode_prints_and_exits_zero(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.main(["--template"]), 0)
        self.assertIn("7", buffer.getvalue())

    def test_a_target_file_is_scanned_alone(self):
        path = os.path.join(self.root, "data", "manuscript", "ch9-test.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# 第9章 测试\n\n## 9.9 延伸思考\n\n1. 练习\n")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--target", "ch9-test.md", "--floor", "0"])
        self.assertIn(code, (0, 1))
        self.assertIn("ch9-test.md", buffer.getvalue())

    def test_a_section_without_a_following_h2_runs_to_the_end(self):
        lines = ["## 1.1 延伸思考\n", "正文\n", "更多\n"]
        self.assertEqual(self.mod.find_section_end(lines, 1), len(lines) + 1)


if __name__ == "__main__":
    unittest.main()
