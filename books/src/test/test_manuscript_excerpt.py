#!/usr/bin/env python3
"""The excerpt tool: print a block from the tree, check it, repair its citation.

The value of the command is that its rules are the gate's rules, so a block it prints must
pass and a drift it reports must be one the gate would report. The cases below hold it to
that: printed output is re-checked, a changed line is drift, and a repair retargets the
citation with elisions instead of rewriting the code.
"""

import io
import os
import unittest
from contextlib import redirect_stdout

from _cases import FixtureCase

TAGS = ("layer:manuscript", "tier:fast")

SOURCE = (
    "package org.demo;\n"  # 1
    "\n"  # 2
    "class Thing {\n"  # 3
    "    int size;\n"  # 4
    "    /** doc */\n"  # 5
    "    int count;\n"  # 6
    "    void run() {\n"  # 7
    "        size++;\n"  # 8
    "    }\n"  # 9
    "}\n"  # 10
)


class ExcerptToolTest(FixtureCase):
    def setUp(self):
        super().setUp()
        self.source = os.path.join(self.tmp.name, "src", "org", "demo")
        os.makedirs(self.source, exist_ok=True)
        with open(os.path.join(self.source, "Thing.java"), "w", encoding="utf-8") as fh:
            fh.write(SOURCE)
        self.tool = self.module("excerpt")
        self.tool._config.source_tree = lambda *_args: os.path.dirname(os.path.dirname(self.source))

    def manuscript(self, text: str) -> str:
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_a_printed_block_is_ready_to_paste(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(self.tool.main(["--file", "org/demo/Thing.java", "--lines", "7-9"]), 0)
        block = out.getvalue()
        self.assertIn("// Thing.java:7-9", block)
        self.assertIn("```java", block)
        self.assertIn("        size++;", block)

    def test_a_printed_block_passes_the_checker(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.tool.main(["--file", "org/demo/Thing.java", "--lines", "7-9"])
        path = self.manuscript(out.getvalue())
        self.assertEqual(self.tool.check(path), [])

    def test_a_cited_span_that_lost_its_code_is_reported(self):
        path = self.manuscript("```java\n// Thing.java:7-9\nvoid run() { size++; }\n```\n")
        problems = self.tool.check(path)
        self.assertEqual(len(problems), 1)
        self.assertIn("not the cited span", problems[0])

    def test_an_elision_makes_the_body_a_subsequence(self):
        path = self.manuscript(
            "```java\n// Thing.java:3-9\nclass Thing {\n// ...\n    void run() {\n"
            "        size++;\n    }\n```\n"
        )
        self.assertEqual(self.tool.check(path), [])

    def test_an_annotation_does_not_count_as_a_change(self):
        path = self.manuscript(
            "```java\n// Thing.java:7-9\nvoid run() {  // 入口\n"
            "        size++;  // 自增\n    }\n```\n"
        )
        self.assertEqual(self.tool.check(path), [])

    def test_repair_retargets_the_citation_and_marks_the_gap(self):
        path = self.manuscript(
            "```java\n// Thing.java:7-9\nclass Thing {\n"
            "    void run() {\n        size++;\n    }\n```\n"
        )
        self.assertEqual(len(self.tool.check(path)), 1)
        self.assertEqual(self.tool.repair(path), 1)
        self.assertEqual(self.tool.check(path), [])
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("// Thing.java:3-9", text)
        self.assertIn("// ...", text)

    def test_a_shown_line_that_is_not_in_the_file_is_not_retargeted(self):
        path = self.manuscript("```java\n// Thing.java:7-9\nvoid stop() {}\n```\n")
        self.assertEqual(self.tool.repair(path), 0)
        self.assertTrue(self.tool.check(path))


class ExcerptEdgeTest(FixtureCase):
    def setUp(self):
        super().setUp()
        self.source = os.path.join(self.tmp.name, "src")
        os.makedirs(os.path.join(self.source, "a", "b"), exist_ok=True)
        with open(os.path.join(self.source, "a", "b", "Thing.java"), "w", encoding="utf-8") as fh:
            fh.write(SOURCE)
        self.tool = self.module("excerpt")
        self.tool._config.source_tree = lambda *_args: self.source

    def manuscript(self, text: str) -> str:
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_a_bare_basename_finds_the_file_in_a_subpackage(self):
        self.assertTrue(self.tool.locate("Thing.java").endswith("a/b/Thing.java"))

    def test_a_missing_file_is_an_error_not_a_traceback(self):
        with self.assertRaises(SystemExit) as caught:
            self.tool.locate("Ghost.java")
        self.assertIn("not found", str(caught.exception))

    def test_quoting_outside_the_file_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            self.tool.block("Thing.java", 9, 99)
        self.assertIn("cannot quote", str(caught.exception))

    def test_a_single_line_quote_has_no_range_in_the_head(self):
        block = self.tool.block("Thing.java", 4)
        self.assertIn("// Thing.java:4-4", block)
        self.assertIn("int size;", block)

    def test_the_body_reader_skips_an_opening_fence(self):
        lines = ["```java", "// Thing.java:4", "int size;", "```"]
        body, _last = self.tool.bodies(lines, 1)
        self.assertEqual(body, ["int size;"])

    def test_a_short_head_that_does_not_match_the_start_is_drift(self):
        path = self.manuscript("```java\n// Thing.java:4\nvoid run() {}\n```\n")
        self.assertIn("does not match", self.tool.check(path)[0])

    def test_a_span_beyond_the_file_is_drift(self):
        path = self.manuscript("```java\n// Thing.java:9-99\nvoid run() {}\n```\n")
        self.assertIn("outside the file", self.tool.check(path)[0])

    def test_a_clean_manuscript_repairs_nothing(self):
        path = self.manuscript(
            "```java\n// Thing.java:7-9\nvoid run() {\n        size++;\n    }\n```\n"
        )
        self.assertEqual(self.tool.repair(path), 0)

    def test_repair_marks_a_gap_between_shown_lines(self):
        path = self.manuscript(
            "```java\n// Thing.java:3-9\nclass Thing {\n"
            "    void run() {\n        size++;\n    }\n```\n"
        )
        self.assertEqual(len(self.tool.check(path)), 1)
        self.assertEqual(self.tool.repair(path), 1)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("// ...", text)
        self.assertEqual(self.tool.check(path), [])

    def test_check_mode_exits_one_with_problems_and_zero_without(self):
        bad = self.manuscript("```java\n// Thing.java:7-9\nvoid stop() {}\n```\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.tool.main(["--check", bad]), 1)
        good = self.manuscript(
            "```java\n// Thing.java:7-9\nvoid run() {\n        size++;\n    }\n```\n"
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.tool.main(["--check", good]), 0)

    def test_repair_mode_reports_what_it_changed(self):
        path = self.manuscript(
            "```java\n// Thing.java:3-9\nclass Thing {\n    void run() {\n    }\n```\n"
        )
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(self.tool.main(["--repair", path]), 0)
        self.assertIn("repaired 1", out.getvalue())

    def test_no_arguments_is_a_usage_error(self):
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()):
                self.tool.main([])


if __name__ == "__main__":
    unittest.main()
