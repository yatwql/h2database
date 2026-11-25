#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""

import os
import sys
import unittest

from _cases import FixtureCase

TAGS = ("layer:manuscript", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestGlossaryValidateMode(FixtureCase):
    def test_validate_resolves_chapters(self):
        code, out = self.run_script("glossary.py", "--validate")
        self.assertIn(code, (0, 1), out[-300:])
        self.assertIn("Entries", out)

    def test_validate_flags_invalid_chapter(self):
        self.write(
            "data/manuscript/back/glossary.md",
            "# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n  **章节**：第99章 §99.1\n",
        )
        code, out = self.run_script("glossary.py", "--validate")
        self.assertEqual(code, 1)
        self.assertIn("INVALID", out)


class TestGlossaryEdgeBranches(FixtureCase):
    """The skip rules in the draft, the no-chapter verdict, the long lists."""

    def test_validate_reports_a_term_without_a_chapter(self):
        self.write(
            "data/manuscript/back/glossary.md", "# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n"
        )
        code, out = self.run_script("glossary.py", "--validate")
        self.assertEqual(code, 1)
        self.assertIn("NO_CHAPTER", out)

    def test_coverage_mode_summarises_a_long_term_list(self):
        glossary = ["# 术语表", "", "## A", ""]
        for i in range(7):
            glossary.append(f"- **术语{i}**: 第{i % 2 + 1}章 §1.{i}\n  **章节**：第1章")
        self.write("data/manuscript/back/glossary.md", "\n".join(glossary) + "\n")
        code, out = self.run_script("glossary.py", "--coverage")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("共7条", out)

    def test_the_draft_skips_markers_and_code_but_keeps_terms(self):
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n"
            "**图 1-1: 架构**\n\n"
            "**本章导读** 与 **注意** 是结构标记。\n\n"
            "**1. 第一步** 与 **1.1 H2 Database 概述** 是标题缩写。\n\n"
            "**run(** 是代码。**MVStore 文件** 是真正的术语。\n",
        )
        code, out = self.run_script("glossary.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("MVStore 文件", out)
        # the file's own header mentions 注意, so check the entry form only
        for skipped in ("本章导读", "注意", "1.1 H2 Database 概述", "run("):
            self.assertNotIn(f"- **{skipped}**", out)


if __name__ == "__main__":
    unittest.main()


class TestGlossaryCoverageMode(FixtureCase):
    def test_coverage_mode_runs(self):
        code, out = self.run_script("glossary.py", "--coverage")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("术语不足", out)
        self.assertNotIn("Traceback", out)

    def test_check_mode_with_rich_glossary(self):
        self.write(
            "data/manuscript/back/glossary.md",
            "# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n"
            "  **章节**：第1章 §1.1\n  **相关**：[[MVStore]]\n\n"
            "## M\n\n- **MVStore**: 存储引擎。\n  **章节**：第2章 §2.1\n",
        )
        code, out = self.run_script("glossary.py", "--check")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("自动生成", out)


class TestGlossaryBuilderBranches(FixtureCase):
    def test_a_missing_glossary_is_regenerated(self):
        os.unlink(os.path.join(self.root, "data", "manuscript", "back", "glossary.md"))
        code, out = self.run_script("glossary.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("自动生成", out)
        self.assertNotIn("Traceback", out)

    def test_check_mode_on_missing_terms(self):
        self.write(
            "data/manuscript/back/glossary.md",
            "# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n  **章节**：第1章 §1.1\n",
        )
        code, out = self.run_script("glossary.py", "--check")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("自动生成", out)
