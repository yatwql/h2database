#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""

import os
import sys
import unittest

from _cases import FixtureCase

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestReadabilityDeep(FixtureCase):
    def test_unbalanced_box_and_bad_caption(self):
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n"
            "```text\n┌────────┐\n│ 缺少下边框 │\n```\n\n"
            "**图 1-1: 架构**\n\n"
            "**图 1-2: 展示组件 A 与组件 B 的完整调用链路与失败回退**\n",
        )
        code, out = self.run_script("readability.py", "--figures")
        self.assertEqual(code, 0, out[-400:])
        self.assertIn("caption too short", out)
        self.assertNotIn("Traceback", out)

    def test_wide_diagram_and_long_lines(self):
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n" + "```text\n" + ("x" * 140 + "\n") * 4 + "```\n",
        )
        code, out = self.run_script("readability.py")
        self.assertIn(code, (0, 1), out[-400:])
        self.assertIn("READABILITY", out)




class TestReadabilityBranches(FixtureCase):
    def test_runs_on_fixture(self):
        code, out = self.run_script("readability.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("READABILITY FAILURES", out)
        self.assertNotIn("Traceback", out)

    def test_long_sentence_and_wide_diagram(self):
        body = "这是一句" + "很长" * 60 + "的话。\n"
        diagram = "```text\n" + "x" * 130 + "\n" + "y" * 130 + "\n" + "z" * 130 + "\n```\n"
        self.write("data/manuscript/ch1-test.md", "# 第1章 测试章节\n\n" + body + "\n" + diagram)
        code, out = self.run_script("readability.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("READABILITY FAILURES", out)

    def test_wide_box_diagram_reports_width_and_corner_mismatch(self):
        wide = "│ " + "x" * 120 + " │"
        diagram = "```text\n┌──┬──┐┐\n" + wide + "\n└──┴──┴──┘\n```\n"
        self.write("data/manuscript/ch1-test.md", "# 第1章 测试章节\n\n" + diagram)
        code, out = self.run_script("readability.py")
        self.assertEqual(code, 0, out[-400:])
        self.assertIn("diagram width", out)
        self.assertIn("┌ (1) != ┐ (2)", out)
        self.assertIn("┬ (1) != ┴ (2)", out)

    def test_stray_diagram_lines_outside_pre(self):
        self.write(
            "dist/test-book.html",
            "<html><body>\n"
            + "│ 一块\n│ 两块\n│ 三块\n"
            + "<pre>\n│ 在围栏里\n</pre>\n"
            + "</body></html>\n",
        )
        code, out = self.run_script("readability.py")
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("diagram-like lines outside", out)

    def test_inline_visual_line_is_accepted_and_trailing_run_closes_at_eof(self):
        self.write("dist/test-book.html", "<html><body>\n┬ 单行\n<p>prose</p>\n│ 一\n│ 二\n│ 三\n")
        code, out = self.run_script("readability.py")
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("blocks: [3]", out)

    def test_two_inline_diagram_lines_are_a_warning_not_a_failure(self):
        self.write(
            "dist/test-book.html", "<html><body>\n│ 一\n│ 二\n<p>prose</p>\n</body></html>\n"
        )
        code, out = self.run_script("readability.py")
        self.assertEqual(code, 0, out[-400:])
        self.assertIn("inline visual-aid lines", out)

    def test_overlong_diagram_block_reports_its_length(self):
        block = "```text\n┌" + "─" * 4 + "┐\n" + "│ 一行\n" * 82 + "└" + "─" * 4 + "┘\n```\n"
        self.write("data/manuscript/ch1-test.md", "# 第1章 测试章节\n\n" + block)
        code, out = self.run_script("readability.py")
        self.assertEqual(code, 0, out[-400:])
        self.assertIn("diagram/code block length", out)


if __name__ == "__main__":
    unittest.main()
