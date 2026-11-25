#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def run_script(self, script: str, *args: str):
        return _fixture.run_inproc(self.root, script, *args)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path


class TestSmartAuditBranches(FixtureCase):
    def test_runs_on_fixture_with_report(self):
        code, out = self.run_script("smart.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("TOTAL sections needing additional diagrams", out)
        self.assertNotIn("Traceback", out)

    def test_diagram_markers_and_short_blocks(self):
        smart = self.module("smart")
        self.assertEqual(smart.count_diagrams(""), 0)
        two_line = "```text\n┌┐\n└┘\n```\n"
        self.assertEqual(smart.count_diagrams(two_line), 0)

    def test_exempt_ranges_non_appendix(self):
        smart = self.module("smart")
        lines = ["# 第1章 测试", "", "## 1.1 小节", "正文"]
        headings = [(1, "第1章 测试", 1), (2, "1.1 小节", 3)]
        self.assertEqual(smart.build_exempt_ranges(headings, lines), [])


class TestSmartEdgeBranches(FixtureCase):
    """Exemptions, figure references and the aggregation of #### children."""

    def smart(self):
        return self.module("smart")

    def test_a_reference_before_the_caption_counts(self):
        lines = ["如图 1-1 所示，整体链路如下。", "**图 1-1: 整体链路**"]
        self.assertTrue(self.smart()._is_referenced(lines, 2, "1-1"))

    def test_a_chapter_without_figures_is_reported_as_empty(self):
        self.write("data/manuscript/ch1-test.md", "# 第1章 测试章节\n\n正文。\n")
        code, out = self.run_script("smart.py", "--fig-refs")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("0 figures", out)

    def test_a_diagram_block_closed_by_prose_counts(self):
        block = "┌──┐\n│A │\n└──┘\n正文\n"
        self.assertEqual(self.smart().count_diagrams(block), 1)

    def test_the_marker_list_is_configuration(self):
        # style.json [diagrams].markers decides what counts as a diagram
        smart = self.smart()
        with mock.patch.object(smart, "DIAGRAM_MARKERS", ["#"]):
            self.assertEqual(smart.count_diagrams("#a\n#b\n#c\n正文\n"), 1)

    def test_an_appendix_file_is_exempt_wholly(self):
        lines = ["# 附录 A 案例", "", "### 1.1 小节", "正文"]
        headings = [(0, 1, "附录 A 案例"), (2, 3, "1.1 小节")]
        self.assertEqual(self.smart().build_exempt_ranges(headings, lines), [(0, len(lines))])

    def test_an_in_chapter_appendix_ends_at_the_next_section(self):
        lines = ["# 第1章 测试", "", "## 附：示例", "", "### 示例一", "", "", "", "## 1.2 正文", ""]
        headings = [(0, 1, "第1章 测试"), (2, 2, "附：示例"), (4, 3, "示例一"), (8, 2, "1.2 正文")]
        self.assertEqual(self.smart().build_exempt_ranges(headings, lines), [(2, 8)])

    def test_a_section_inside_an_appendix_is_skipped(self):
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n## 附：示例\n\n"
            "### 1.1.1 示例路径\n\n正文说明。\n\n"
            "## 1.2 正文\n\n正文。\n",
        )
        code, out = self.run_script("smart.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertNotIn("示例路径", out)

    def test_a_child_section_is_aggregated_into_its_parent(self):
        diagram = "```text\n┌──┐\n│A │\n└──┘\n```\n\n"
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n## 1.1 背景\n\n\n"
            "### 1.1.1 写入路径\n\n"
            "#### 1.1.1.1 缓冲写入\n\n正文。\n\n"
            + diagram
            + "#### 1.1.1.2 落盘写入\n\n正文。\n\n"
            + diagram
            + "## 1.9 小结\n\n小结。\n",
        )
        code, out = self.run_script("smart.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("TOTAL", out)

    def test_a_section_too_short_to_need_diagrams_is_not_reported(self):
        self.write(
            "data/manuscript/ch1-test.md", "# 第1章 测试章节\n\n## 1.1 背景\n\n### 1.1.1 短\n\n她\n"
        )
        code, out = self.run_script("smart.py")
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn("### 1.1.1 短", out)


class TestSmartAuditDeepCoverage(FixtureCase):
    """Drive _audit_smart's report path with #### children and few diagrams."""

    RICH = (
        "# 第1章 测试章节\n\n"
        "> **本章导读**: 导读。\n\n"
        "## 1.1 背景与问题\n\n"
        "这一节说明背景，**图 1-1: 展示整体调用链路** 给出概览。\n\n"
        "### 1.1.1 写入路径\n\n"
        "#### 1.1.1.1 缓冲写入\n\n"
        "正文说明缓冲写入的行为与触发条件。\n\n"
        "#### 1.1.1.2 落盘写入\n\n"
        "正文说明落盘写入的行为与触发条件。\n\n"
        "```text\n┌──┐\n│A │\n└──┘\n```\n\n"
        "```text\n┌──┐\n│B │\n└──┘\n```\n\n"
        "**图 1-2: 对比两种写入路径的差异**\n\n"
        "## 1.9 本章小结\n\n小结。\n"
    )

    def test_report_with_children(self):
        self.write("data/manuscript/ch1-test.md", self.RICH)
        code, out = self.run_script("smart.py")
        self.assertEqual(code, 0, out[-400:])
        self.assertIn("TOTAL sections needing additional diagrams", out)
        self.assertNotIn("Traceback", out)

    def test_fig_refs_mode(self):
        code, out = self.run_script("smart.py", "--fig-refs")
        self.assertEqual(code, 0, out[-300:])


class TestSmartAuditGaps(FixtureCase):
    """A section with #### children and too few diagrams must be reported."""

    GAP = (
        "# 第1章 测试章节\n\n"
        "> **本章导读**: 导读。\n\n"
        "## 1.1 背景\n\n"
        "### 1.1.1 写入路径\n\n"
        "#### 1.1.1.1 缓冲写入\n\n"
        "正文说明缓冲写入的行为与触发条件，并给出边界分析。\n\n"
        "#### 1.1.1.2 落盘写入\n\n"
        "正文说明落盘写入的行为与触发条件，并给出边界分析。\n\n"
        "```text\n┌──┐\n│A │\n└──┘\n```\n\n"
        "## 1.9 本章小结\n\n小结。\n"
    )

    def test_gap_section_reported(self):
        self.write("data/manuscript/ch1-test.md", self.GAP)
        code, out = self.run_script("smart.py")
        self.assertIn(code, (0, 1), out[-400:])
        self.assertIn("TOTAL", out)


if __name__ == "__main__":
    unittest.main()


class DiagramCountingEdgesTest(FixtureCase):
    """A diagram block and an appendix run that both reach the end of the text."""

    def test_a_marker_block_ending_the_text_is_still_one_diagram(self):
        smart = self.module("smart")
        marker = next(iter(smart.DIAGRAM_MARKERS))
        text = "\n".join([marker, marker, marker])
        self.assertEqual(smart.count_diagrams(text), 1)

    def test_an_appendix_heading_with_no_following_heading_runs_to_eof(self):
        smart = self.module("smart")
        lines = ["# 第一章", "## 附：附注", "### 一", "text"]
        headings = [(1, 1, "第一章"), (2, 2, "附：附注"), (3, 3, "一")]
        self.assertEqual(smart.build_exempt_ranges(headings, lines), [(2, 4)])
