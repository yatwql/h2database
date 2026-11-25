#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
"""

import json
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


class TestBalanceCheckHelpers(FixtureCase):
    def test_count_lines(self):
        bc = self.module("balance")
        self.assertEqual(bc.count_lines("a\nb\nc\n"), 3)

    def test_count_figures(self):
        bc = self.module("balance")
        text = "**图 1-1: 展示**\n**图 2-3: 对比**\n**图 A-1: 标注**\n"
        self.assertEqual(bc.count_figures(text), 3)

    def test_count_source_refs(self):
        bc = self.module("balance")
        self.assertEqual(bc.count_source_refs("见 MVStore.java:12 与 Page.java:7"), 2)

    def test_glossary_chapter_index(self):
        bc = self.module("balance")
        index = bc.load_glossary_chapter_index()
        self.assertIsInstance(index, dict)
        self.assertTrue(index, "fixture glossary should contribute chapter hits")

    def test_load_index_chapter_index_counts_entries_per_chapter(self):
        bc = self.module("balance")
        index_md = self.write(
            "data/manuscript/back/index.md",
            "# 索引\n\n- **MVStore** —— §3.2\n- **事务** —— §3.4, §7.1\n",
        )
        self.assertTrue(index_md)
        self.assertEqual(bc.load_index_chapter_index(), {3: 2, 7: 1})

    def test_collect_metrics_and_render(self):
        bc = self.module("balance")
        metrics = bc.collect_metrics()
        self.assertIn("totals", metrics)
        self.assertGreaterEqual(metrics["totals"]["files"], 1)
        rendered = bc.render_markdown(metrics)
        self.assertIn("| 文件 |", rendered)

    def test_render_diff_shows_the_direction_of_each_change(self):
        bc = self.module("balance")
        current = bc.collect_metrics()
        baseline = json.loads(json.dumps(current))
        for row in baseline["files"]:
            row["lines"] += 2
        diff = bc.render_diff(current, baseline)
        self.assertIn("| 文件 |", diff)
        self.assertIn("(-2)", diff)

    def test_missing_glossary_and_index_contribute_no_counts(self):
        bc = self.module("balance")
        for rel in ("data/manuscript/back/glossary.md", "data/manuscript/back/index.md"):
            os.remove(os.path.join(self.root, rel))
        self.assertEqual(bc.load_glossary_chapter_index(), {})
        self.assertEqual(bc.load_index_chapter_index(), {})

    def test_metrics_skip_a_chapter_file_that_is_absent(self):
        bc = self.module("balance")
        os.remove(os.path.join(self.root, "data/manuscript/ch2-test.md"))
        metrics = bc.collect_metrics()
        names = [row["file"] for row in metrics["files"]]
        self.assertNotIn("ch2-test.md", names)
        self.assertGreaterEqual(metrics["totals"]["files"], 1)

    def test_metrics_without_any_chapter_file_report_zero_totals(self):
        bc = self.module("balance")
        for rel in ("ch1-test.md", "ch2-test.md"):
            os.remove(os.path.join(self.root, "data/manuscript", rel))
        metrics = bc.collect_metrics()
        self.assertEqual(metrics["files"], [])
        self.assertEqual(metrics["balance"]["max_min_ratio"], 0.0)
        self.assertEqual(metrics["balance"]["stddev_lines"], 0.0)
        self.assertIn("均衡指标", bc.render_markdown(metrics))

    def test_render_diff_marks_files_added_and_dropped(self):
        bc = self.module("balance")
        current = bc.collect_metrics()
        baseline = json.loads(json.dumps(current))
        dropped = baseline["files"].pop(0)
        baseline["files"].append({**dropped, "file": "retired.md"})
        diff = bc.render_diff(current, baseline)
        self.assertIn("`retired.md` ❌", diff)
        self.assertIn("🆕", diff)


if __name__ == "__main__":
    unittest.main()
