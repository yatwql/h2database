#!/usr/bin/env python3
"""Prose-quality score: the anchors, the table reader and the two verdict exits."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

TOTALS = {
    "avg_sentence": 20.0,
    "long_sentence_ratio": 5.0,
    "avg_paragraph": 200.0,
    "bullet_ratio": 10.0,
    "coords_per_file": 25.0,
    "h3_per_file": 8.0,
    "duplicate_ratio": 2.0,
    "empty_cell_ratio": 0.0,
}


class ProseQualitySurfacesTest(unittest.TestCase):
    """The score anchors, the table reader and the two verdict exits."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "prose_quality")

    def test_the_score_clamps_at_both_anchors(self):
        self.assertEqual(self.mod._score(50, 28, 45, higher_is_better=False), 0.0)
        self.assertEqual(self.mod._score(10, 28, 45, higher_is_better=False), 100.0)
        self.assertAlmostEqual(self.mod._score(30, 28, 45, higher_is_better=False), 100 * 15 / 17)
        self.assertEqual(self.mod._score(0, 20, 4), 0.0)
        self.assertEqual(self.mod._score(30, 20, 4), 100.0)
        self.assertAlmostEqual(self.mod._score(12, 20, 4), 50.0)

    def test_a_table_at_the_end_of_the_text_is_measured(self):
        rows, empty, ragged = self.mod._table_metrics("| a | b |\n|---|---|\n| 1 |  |\n")
        self.assertEqual((rows, empty, ragged), (2, 1, 0))

    def test_a_ragged_table_is_counted(self):
        rows, _empty, ragged = self.mod._table_metrics(
            "| a | b |\n|---|---|\n| 1 | 2 |\n| 1 | 2 | 3 |\n"
        )
        self.assertEqual((rows, ragged), (3, 3))

    def test_a_table_without_a_body_is_skipped(self):
        self.assertEqual(self.mod._table_metrics("|---|---|\n|---|---|\n"), (0, 0, 0))

    def test_a_clean_report_states_the_verdict(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "measure", return_value={"totals": TOTALS}),
            mock.patch.object(self.mod, "score", return_value=(99.0, {"x": 99.0})),
            mock.patch.dict(self.mod._config.STYLE_POLICY, {"prose": {"min_composite": 80}}),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main([]), 0)
        self.assertIn("文风评分达标", buffer.getvalue())

    def test_a_score_below_the_target_fails_unless_warn_only(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "measure", return_value={"totals": TOTALS}),
            mock.patch.object(self.mod, "score", return_value=(10.0, {"x": 10.0})),
            mock.patch.dict(self.mod._config.STYLE_POLICY, {"prose": {"min_composite": 80}}),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main([]), 1)
            self.assertEqual(self.mod.main(["--warn-only"]), 0)
        self.assertIn("未达目标", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()


class ProseTableEdgesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "prose_quality")

    def test_a_table_that_ends_the_text_is_still_measured(self):
        rows, _empty, _ragged = self.mod._table_metrics("| 名称 | 值 |\n| --- | --- |\n| a | 1 |")
        self.assertEqual(rows, 2)
