#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture
from _cases import FixtureCase

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestIndexXrefBranches(FixtureCase):
    def test_runs_and_reports(self):
        code, out = self.run_script("index_xrefs.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("issues:          0", out)
        self.assertNotIn("Traceback", out)

    def test_an_empty_target_is_skipped_and_a_prefixed_one_is_resolved(self):
        self.write(
            "data/manuscript/back/index.md",
            "# 索引\n\n## A\n\n- ACID —— §1.1\n"
            "  see also:\n"
            "  see also: 见 ACID\n"
            "  see also: see ACID\n",
        )
        code, out = self.run_script("index_xrefs.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("every see-also target resolves", out)

    def test_an_invalid_sub_entry_chapter_is_reported(self):
        self.write(
            "data/manuscript/back/index.md",
            "# 索引\n\n## A\n\n- ACID —— §1.1\n  - 原子性 —— §9.9\n",
        )
        code, out = self.run_script("index_xrefs.py")
        self.assertEqual(code, 1, out[-300:])
        self.assertIn("references invalid", out)
        self.assertIn("issues:          1", out)

    def test_broken_see_also_detected(self):
        self.write(
            "data/manuscript/back/index.md",
            "# 索引\n\n## A\n\n- ACID —— §1.1\n  see also: 不存在的词\n",
        )
        code, out = self.run_script("index_xrefs.py")
        self.assertEqual(code, 1, out[-300:])
        self.assertIn("issues:          1", out)




class IndexXrefParserEdgesTest(unittest.TestCase):
    """Alias forms, a bare entry, odd declared chapters, and the truncated lists."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), "index_xrefs"
        )

    def test_aliases_come_out_of_both_paren_forms(self):
        aliases = self.mod._aliases_for("MVStore（存储引擎）(store)")
        self.assertIn("存储引擎", aliases)
        self.assertIn("store", aliases)

    def test_an_entry_without_an_explicit_reference_keeps_its_term(self):
        term, ref_text, chapters = self.mod._term_and_refs("- 孤立条目")
        self.assertEqual((term, ref_text, chapters), ("孤立条目", "", []))

    def test_a_declared_chapter_that_is_not_a_number_is_skipped(self):
        with mock.patch.object(
            self.mod._config, "chapter_coverage", lambda: {"ch1-x.md": [1, "nope"], "cover.md": [9]}
        ):
            self.assertEqual(self.mod.declared_chapters(), {1})

    def test_a_see_also_list_longer_than_twenty_is_truncated_in_the_report(self):
        targets = [f"不存在{i}" for i in range(25)]
        see_alsos = [{"line": 1, "parent": "A", "targets": targets}]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            dangling = self.mod._check_see_also({"A"}, {}, see_alsos)
        self.assertEqual(dangling, 25)
        self.assertIn("and 5 more", buffer.getvalue())

    def test_an_invalid_sub_entry_list_longer_than_twenty_is_truncated(self):
        subs = [
            {"line": index, "parent": "A", "term": f"t{index}", "chapters": [99]}
            for index in range(25)
        ]
        buffer = io.StringIO()
        with mock.patch.object(self.mod, "declared_chapters", lambda: {1}), redirect_stdout(buffer):
            bad = self.mod._check_sub_entry_chapters(subs)
        self.assertEqual(bad, 25)
        self.assertIn("and 5 more", buffer.getvalue())

    def test_sections_out_of_alphabetical_order_are_reported(self):
        sections = [("B", 10), ("A", 20), ("附录", 30)]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            bad = self.mod._check_section_order(sections)
        self.assertEqual(bad, 1)
        self.assertIn("out of order", buffer.getvalue())

    def test_a_category_suffix_that_leaves_nothing_is_not_an_alias(self):
        # '类' is itself a trailing category suffix: stripping it leaves "",
        # so the only alias left is the term as written.
        self.assertEqual(self.mod._aliases_for("类"), {"类"})

    def test_a_slash_with_nothing_after_it_adds_no_alias(self):
        # the split on '/' yields one empty piece, which must not become an alias
        self.assertEqual(self.mod._aliases_for("A  /  "), {"A", "A  /", "A  /  "})

    def test_a_line_that_is_neither_an_entry_nor_a_reference_parts_to_nothing(self):
        self.assertEqual(self.mod._term_and_refs("-"), ("", "", []))

    def test_a_sub_entry_before_any_main_entry_is_dropped(self):
        path = os.path.join(self.tmp.name, "index.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# 索引\n\n  - 孤立子项 —— §1.1\n\n## A\n\n- ACID —— §1.1\n")
        main_entries, sub_entries, _, sections = self.mod.parse_index(path)
        self.assertEqual(sub_entries, [])
        self.assertEqual(sorted(main_entries), ["ACID"])
        self.assertEqual(sections, [("A", 5)])

    def test_a_see_also_target_that_is_only_a_prefix_is_skipped(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            dangling = self.mod._check_see_also(
                {"ACID"}, {}, [{"line": 7, "parent": "ACID", "targets": [""]}]
            )
        self.assertEqual(dangling, 0)
        self.assertIn("every see-also target resolves", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
