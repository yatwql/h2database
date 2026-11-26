#!/usr/bin/env python3
"""Marker planning: put generated blocks into a chapter that was written first.

The rule read here is book-neutral: the skeleton says where a block belongs (the
heading above it) and the plan finds the same section in the existing prose — by
title, then by section number among related titles, then by nothing (append).
"""

from __future__ import annotations

import argparse
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:ingest", "tier:fast")

_fixture.ensure_tools_path()

SKELETON = """# 第1章 架构

## 1.1 概览

## 1.2 包结构

<!-- generated:packages -->
| 包 | 文件数 |
<!-- /generated -->

## 1.3 依赖方向

<!-- generated:deps -->
| 依赖 | 次数 |
<!-- /generated -->
"""

PROSE = """# 第1章 架构

## 1.1 概览

手写的正文，一个字都不该被改动。

## 1.2 包与模块

手写的包表。

## 1.3 依赖方向

手写的依赖说明。
"""


class MarkerParseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.blocks = _fixture.load_module(self.root, "factblocks")

    def test_a_skeleton_gives_back_its_blocks_and_their_headings(self):
        blocks = self.blocks.blocks_from_skeleton(SKELETON)
        self.assertEqual(sorted(blocks), ["deps", "packages"])
        self.assertEqual(blocks["packages"], ["| 包 | 文件数 |"])
        self.assertEqual(self.blocks.block_headings(SKELETON)["packages"], "## 1.2 包结构")

    def test_a_stray_close_marker_is_ignored(self):
        blocks = self.blocks.blocks_from_skeleton("<!-- /generated -->\n正文\n")
        self.assertEqual(blocks, {})

    def test_an_open_marker_left_at_the_end_is_reported(self):
        state = self.blocks.marker_names("<!-- generated:a -->\n| x |\n")
        self.assertEqual(state["unclosed"], ["a"])

    def test_a_second_open_marker_leaves_the_first_unclosed(self):
        state = self.blocks.marker_names(
            "<!-- generated:a -->\n| x |\n\n<!-- generated:b -->\n| y |\n<!-- /generated -->\n"
        )
        self.assertEqual(state["unclosed"], ["a"])
        self.assertEqual(state["present"], ["a", "b"])

    def test_existing_markers_report_duplicates_and_unclosed_blocks(self):
        state = self.blocks.marker_names(
            PROSE.replace(
                "## 1.1 概览",
                "## 1.1 概览\n\n<!-- generated:packages -->\n| a |\n"
                "<!-- /generated -->\n\n"
                "<!-- generated:packages -->\n| b |\n"
                "<!-- /generated -->",
            )
            + "\n<!-- generated:deps -->\n| c |\n"
        )
        self.assertEqual(state["duplicated"], ["packages"])
        self.assertEqual(state["unclosed"], ["deps"])


class AnchorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.blocks = _fixture.load_module(_fixture.build_book(self.tmp.name), "factblocks")

    def lines(self, text: str) -> list[str]:
        return text.splitlines()

    def test_the_same_title_wins(self):
        line, why = self.blocks.suggest_anchor(self.lines(PROSE), "## 1.3 依赖方向")
        self.assertEqual((line, why), (11, "## 1.3 依赖方向"))

    def test_a_renamed_title_matches_by_section_number(self):
        # the prose calls it 「包与模块」: the number is what survives a rewrite
        line, why = self.blocks.suggest_anchor(self.lines(PROSE), "## 1.2 包结构")
        self.assertEqual((line, why), (7, "## 1.2 包与模块"))

    def test_a_reused_number_does_not_win_over_the_title(self):
        # 1.5 exists in the prose for something else; the closest title must decide
        text = PROSE + "\n## 1.5 延伸思考\n\n题目。\n"
        line, why = self.blocks.suggest_anchor(self.lines(text), "## 1.5 延伸思考")
        self.assertEqual(why, "## 1.5 延伸思考")
        others = self.blocks.suggest_anchor(self.lines(text), "## 1.6 常见疑问")
        self.assertEqual((others[0], others[1]), (0, "（章末）"))

    def test_a_related_title_with_the_same_number_wins_the_tie_break(self):
        text = PROSE.replace("## 1.2 包与模块", "## 1.2 包结构总览")
        line, why = self.blocks.suggest_anchor(self.lines(text), "## 1.2 包结构")
        self.assertEqual(why, "## 1.2 包结构总览")

    def test_nothing_similar_appends_at_the_end(self):
        self.assertEqual(
            self.blocks.suggest_anchor(self.lines(PROSE), "## 9.9 完全无关"), (0, "（章末）")
        )
        self.assertEqual(self.blocks.suggest_anchor(self.lines(PROSE), ""), (0, "（章末）"))


class InsertTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.blocks = _fixture.load_module(_fixture.build_book(self.tmp.name), "factblocks")

    def test_a_block_goes_before_its_anchor_and_keeps_the_prose(self):
        updated = self.blocks.insert_block(PROSE, 7, "packages", ["| 包 | 文件数 |"])
        self.assertIn("<!-- generated:packages -->", updated)
        self.assertLess(updated.index("generated:packages"), updated.index("## 1.2 包与模块"))
        self.assertIn("手写的包表。", updated)
        self.assertIn("手写的正文，一个字都不该被改动。", updated)

    def test_line_zero_appends_at_the_end(self):
        updated = self.blocks.insert_block(PROSE, 0, "deps", ["| 依赖 | 次数 |"])
        self.assertTrue(updated.rstrip().endswith("<!-- /generated -->"))
        self.assertLess(updated.index("手写的依赖说明"), updated.index("generated:deps"))

    def test_the_plan_lists_what_is_missing_and_where(self):
        blocks = self.blocks.blocks_from_skeleton(SKELETON)
        headings = self.blocks.block_headings(SKELETON)
        plan = self.blocks.plan_insertions(PROSE, blocks, headings)
        self.assertEqual(plan["missing"], ["packages", "deps"])
        self.assertEqual([item["name"] for item in plan["plan"]], ["packages", "deps"])
        self.assertEqual(plan["plan"][0]["line"], 7)


class MarkerModeTest(unittest.TestCase):
    """The CLI path: report first, write only with --apply."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, "chapters")
        self.name = next(iter(self.chapters.CHAPTER_SPEC))
        self.path = os.path.join(self.root, "data", "manuscript", self.name)
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(PROSE)
        self.outline = {"chapters": [{"file": self.name, "packages": {}, "source_lines": 10}]}

    def args(self, *, insert: bool = False, apply: bool = False) -> argparse.Namespace:
        return argparse.Namespace(
            only=None, check_markers=not insert, insert_markers=insert, apply=apply
        )

    def run_mode(self, **kwargs) -> str:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.chapters._marker_mode(self.outline, self.args(**kwargs))
        return buffer.getvalue()

    def test_the_report_names_the_missing_blocks_and_writes_nothing(self):
        before = open(self.path, encoding="utf-8").read()
        out = self.run_mode()
        self.assertIn("标记 0/", out)
        self.assertIn("缺 ", out)
        self.assertEqual(open(self.path, encoding="utf-8").read(), before)

    def test_inserting_without_apply_only_previews(self):
        before = open(self.path, encoding="utf-8").read()
        out = self.run_mode(insert=True)
        self.assertIn("--apply", out)
        self.assertEqual(open(self.path, encoding="utf-8").read(), before)

    def test_only_limits_the_report_to_one_chapter(self):
        args = self.args()
        args.only = "ch99-other.md"
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.chapters._marker_mode(self.outline, args)
        self.assertEqual(buffer.getvalue(), "")

    def test_a_chapter_the_generator_does_not_know_is_skipped(self):
        outline = {
            "chapters": [{"file": "appendix-z-unknown.md", "packages": {}, "source_lines": 1}]
        }
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.chapters._marker_mode(outline, self.args())
        self.assertEqual(buffer.getvalue(), "")

    def test_a_duplicated_marker_is_warned_about(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                PROSE + "\n<!-- generated:packages -->\n| a |\n<!-- /generated -->\n"
                "\n<!-- generated:packages -->\n| b |\n<!-- /generated -->\n"
            )
        out = self.run_mode()
        self.assertIn("duplicated: packages", out)

    def test_the_dispatch_reaches_the_marker_mode(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(self.chapters, "_load_state", return_value=({}, self.outline)),
            redirect_stdout(buffer),
        ):
            code = self.chapters.main(["--check-markers"])
        self.assertEqual(code, 0)
        self.assertIn("标记", buffer.getvalue())

    def test_apply_writes_the_blocks_and_keeps_every_prose_line(self):
        out = self.run_mode(insert=True, apply=True)
        self.assertIn("markers inserted", out)
        after = open(self.path, encoding="utf-8").read()
        self.assertIn("generated:packages", after)
        for line in PROSE.splitlines():
            if line.strip():
                self.assertIn(line, after)


if __name__ == "__main__":
    unittest.main()
