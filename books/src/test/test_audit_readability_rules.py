#!/usr/bin/env python3
"""readability: box closure, caption quality, fences and the HTML check.

Each check appends to a module-level list, so a case clears it first and then
asserts the wording — that is what makes the report trustworthy.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class ReadabilityRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "readability")
        self.mod.warnings.clear()
        self.mod.failures.clear()
        self.addCleanup(self.mod.warnings.clear)
        self.addCleanup(self.mod.failures.clear)

    # -- box closure -----------------------------------------------------
    def test_a_balanced_box_draws_no_warning(self):
        self.mod.check_box_closure(["┌──┐", "│  │", "└──┘"], 5, "x.md")
        self.assertEqual(self.mod.warnings, [])

    def test_each_unpaired_corner_is_named(self):
        self.mod.check_box_closure(["┌──┐", "│  │", "└──┤", "┬──┴", "┌──┐"], 5, "x.md")
        text = "\n".join(self.mod.warnings)
        self.assertIn("└", text)  # └ != ┘
        self.assertIn("├", text)  # ├ != ┤
        self.assertTrue(self.mod.warnings)

    def test_a_block_without_box_characters_is_ignored(self):
        self.mod.check_box_closure(["plain text", "more text"], 5, "x.md")
        self.assertEqual(self.mod.warnings, [])

    # -- caption quality -------------------------------------------------
    def test_a_short_caption_is_reported(self):
        self.mod.check_caption_quality("x.md", ["**图 1-1: 架构**"])
        self.assertTrue(any("caption too short" in w for w in self.mod.warnings))

    def test_a_caption_without_a_verb_is_reported(self):
        self.mod.check_caption_quality("x.md", ["**图 1-2: 三个组件的名字**"])
        self.assertTrue(any("caption may lack verb" in w for w in self.mod.warnings))

    def test_a_good_caption_is_silent(self):
        self.mod.check_caption_quality("x.md", ["**图 1-3: 写入流程与目录布局的关系**"])
        self.assertEqual(self.mod.warnings, [])

    def test_caption_checks_only_run_when_asked(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n**图 9-9: 架构**\n")
        self.mod.warnings.clear()
        self.mod.main([])
        self.assertFalse(any("caption too short" in w for w in self.mod.warnings))
        self.mod.warnings.clear()
        self.mod.main(["--figures"])
        self.assertTrue(any("caption too short" in w for w in self.mod.warnings))

    # -- fences and the html check ---------------------------------------
    def test_an_unclosed_fence_is_a_failure(self):
        failures = self.mod._scan_fences("x.md", ["```text", "a", "b"])
        self.assertTrue(any("unclosed fence" in f for f in failures))

    def test_a_caption_inside_a_fence_is_a_failure(self):
        failures = self.mod._scan_fences("x.md", ["```text", "**图 1-1: 架构**", "```"])
        self.assertTrue(any("caption inside fence" in f for f in failures))

    def test_a_wider_than_allowed_diagram_is_a_warning(self):
        wide = "┌" + "─" * 130 + "┐"
        self.mod._scan_fences("x.md", ["```text", wide, "└" + "─" * 130 + "┘", "```"])
        self.assertTrue(any("diagram width" in w for w in self.mod.warnings))

    def test_diagram_lines_outside_pre_are_reported(self):
        html = os.path.join(self.root, "dist", "test-book.html")
        os.makedirs(os.path.dirname(html), exist_ok=True)
        with open(html, "w", encoding="utf-8") as fh:
            fh.write("<p>┌──┐</p>\n<p>│  │</p>\n<p>└──┘</p>\n")
        self.mod.failures.clear()
        self.mod._check_html()
        self.assertTrue(any("outside <pre>" in f for f in self.mod.failures))

    def test_without_html_the_check_is_skipped(self):
        self.mod.failures.clear()
        self.mod._check_html()
        self.assertEqual(self.mod.failures, [])

    # -- box-drawing baseline --------------------------------------------
    def _box_path(self):
        return self.mod.box_baseline_path()

    def _write_baseline(self, files):
        import json

        os.makedirs(os.path.dirname(self._box_path()), exist_ok=True)
        with open(self._box_path(), "w", encoding="utf-8") as fh:
            json.dump({"note": "recorded", "files": files}, fh)

    def test_box_counts_group_warnings_per_manuscript_file(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        self.mod.check_box_closure(["┌──┐", "└──┤"], 3, path)
        self.mod.check_box_closure(["┬──┴"], 9, path)
        self.mod.warnings.append("not a box warning")
        counts = self.mod.box_closure_counts(self.mod.warnings)
        self.assertEqual(counts, {"ch1-test.md": 2})

    def test_a_missing_baseline_accepts_nothing(self):
        self.assertEqual(self.mod.load_box_baseline(), {})

    def test_a_baseline_without_a_file_map_accepts_nothing(self):
        os.makedirs(os.path.dirname(self._box_path()), exist_ok=True)
        with open(self._box_path(), "w", encoding="utf-8") as fh:
            fh.write('{"files": "not a map"}')
        self.assertEqual(self.mod.load_box_baseline(), {})

    def test_a_recorded_baseline_round_trips(self):
        self.mod.save_box_baseline({"ch1-test.md": 4})
        self.assertEqual(self.mod.load_box_baseline(), {"ch1-test.md": 4})

    def test_a_rising_count_is_reported_and_fails(self):
        self._write_baseline({"ch1-test.md": 1})
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        self.mod.check_box_closure(["┌──┐", "└──┤"], 3, path)
        self.mod.check_box_closure(["┬──┴"], 9, path)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([])
        self.assertEqual(code, 1, buffer.getvalue())
        self.assertIn("ch1-test.md: 2 box-drawing warning(s) > accepted 1", buffer.getvalue())

    def test_a_warning_the_baseline_never_saw_fails(self):
        self._write_baseline({"other.md": 3})
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        self.mod.check_box_closure(["┌──┐", "└──┤"], 3, path)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.main([]), 1)
        self.assertIn("ch1-test.md", buffer.getvalue())

    def test_a_shrinking_count_passes_and_asks_for_a_tightening(self):
        self._write_baseline({"ch1-test.md": 5})
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([])
        self.assertEqual(code, 0, buffer.getvalue())
        self.assertIn("--update-baseline", buffer.getvalue())

    def test_update_baseline_records_the_current_counts(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        self.mod.check_box_closure(["┌──┐", "└──┤"], 3, path)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--update-baseline"])
        self.assertEqual(code, 0, buffer.getvalue())
        self.assertEqual(self.mod.load_box_baseline(), {"ch1-test.md": 2})

    def test_json_mode_carries_the_box_drawing_tally(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.mod.main(["--json"])
        self.assertIn('"box_drawing"', buffer.getvalue())

    def test_json_mode_emits_both_lists(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--json"])
        self.assertEqual(code, 0, buffer.getvalue()[-300:])
        self.assertIn('"failures"', buffer.getvalue())
        self.assertIn('"warnings"', buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
