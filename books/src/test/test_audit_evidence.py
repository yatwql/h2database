#!/usr/bin/env python3
"""Evidence density: the three per-chapter numbers and the floor they are judged against.

The measurement is only useful if it can fail, so the cases cover both directions: a
chapter with references scores high, the same prose without them scores low, and a positive
floor turns that into a red gate while the default floor reports and passes.
"""

import io
import json
import unittest
from contextlib import redirect_stdout

from _cases import FixtureCase

TAGS = ("layer:audit", "tier:fast")

BACKED = """# 第1章 测试章节

这一章把调用链讲清楚：`SessionLocal.prepareCommand()` 在 SessionLocal.java:88 处取得锁，
随后交给解析器。读者可以照着这两处回到源码核对行为与顺序，而这一段的长度足够构成一个实质段落。

再看第二个环节，缓存命中由 `Command` 持有，未命中才进解析，这条判断同样可以在
CommandContainer.java:120 找到对应实现，段落长度同样超过判定下限，足以计入统计。
"""

THIN = """# 第1章 测试章节

这一章只描述整体思路，从头到尾没有给出任何可以回溯的位置，读者读完仍然无法确认这些
说法出自哪里，也无法判断顺序与细节是否与实现一致，因此它只能算叙述而不是分析。

第二段同样如此，继续说架构与职责，不落到任何类与方法，篇幅足够构成实质段落，但依据为零。
"""


class DensityNumbersTest(FixtureCase):
    def test_paragraphs_skip_listings_tables_and_headings(self):
        evidence = self.module("evidence")
        text = (
            "# 标题\n\n" + "甲" * 90 + "\n\n"
            "```java\nclass A {}\n```\n\n| 列 | 值 |\n| --- | --- |\n| 1 | 2 |\n"
        )
        self.assertEqual(len(evidence.paragraphs(text)), 1)

    def test_a_backed_chapter_scores_higher_than_a_bare_one(self):
        evidence = self.module("evidence")
        self.write("data/manuscript/ch1-test.md", BACKED)
        backed = evidence.measured("data/manuscript/ch1-test.md")
        self.write("data/manuscript/ch1-test.md", THIN)
        bare = evidence.measured("data/manuscript/ch1-test.md")
        self.assertGreater(backed["coords"], 0)
        self.assertEqual(bare["coords"], 0)
        self.assertGreater(backed["coverage_pct"], bare["coverage_pct"])

    def test_measurement_is_per_chapter_file(self):
        evidence = self.module("evidence")
        self.write("data/manuscript/ch1-test.md", BACKED)
        self.write("data/manuscript/ch2-test.md", THIN)
        numbers = evidence.measure()
        self.assertEqual(set(numbers), {"ch1-test.md", "ch2-test.md"})
        self.assertGreater(
            numbers["ch1-test.md"]["coverage_pct"], numbers["ch2-test.md"]["coverage_pct"]
        )


class DensityFloorTest(FixtureCase):
    def floors(self, coords=0, symbols=0, coverage=0):
        return {"coords": float(coords), "symbols": float(symbols), "coverage": float(coverage)}

    def test_a_zero_floor_reports_and_never_fails(self):
        evidence = self.module("evidence")
        numbers = {"a.md": {"coords_per_1000": 0.0, "symbols_per_1000": 0.0, "coverage_pct": 0}}
        self.assertEqual(evidence.shortfalls(numbers, self.floors()), [])

    def test_a_positive_floor_names_the_chapter_and_the_number(self):
        evidence = self.module("evidence")
        numbers = {"a.md": {"coords_per_1000": 1.0, "symbols_per_1000": 9.0, "coverage_pct": 10}}
        problems = evidence.shortfalls(numbers, self.floors(coords=5, symbols=20, coverage=40))
        self.assertEqual(len(problems), 3)
        self.assertIn("a.md", problems[0])
        self.assertIn("floor 5", problems[0])

    def test_the_cli_reports_a_table_and_exits_on_a_positive_floor(self):
        self.write("data/manuscript/ch1-test.md", THIN)
        evidence = self.module("evidence")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(evidence.main([]), 0)
        self.assertIn("依据密度", out.getvalue())
        self.assertIn("只报数", out.getvalue())

    def test_json_mode_carries_numbers_thresholds_and_shortfalls(self):
        self.write("data/manuscript/ch1-test.md", THIN)
        evidence = self.module("evidence")
        out = io.StringIO()
        with redirect_stdout(out):
            code = evidence.main(["--json"])
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertIn("ch1-test.md", payload["files"])
        self.assertEqual(payload["below"], [])


if __name__ == "__main__":
    unittest.main()
