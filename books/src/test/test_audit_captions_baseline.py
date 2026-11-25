#!/usr/bin/env python3
"""Captions gate: JSON output, baseline diff and the failure threshold."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()


class CaptionsBaselineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_captions(self, *args: str) -> tuple[int, str]:
        return _fixture.run_inproc(self.root, "captions.py", *args)

    def baseline(self, payload: dict) -> str:
        path = os.path.join(self.tmp.name, "captions.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return path

    def test_json_output_has_the_expected_shape(self):
        code, out = self.run_captions("--json")
        payload = json.loads(out[out.index("{") :])
        self.assertEqual(code, 0, out[-300:])
        for key in ("threshold", "count", "violations"):
            self.assertIn(key, payload)

    def test_diff_reports_new_and_fixed_entries(self):
        baseline = self.baseline(
            {"count": 1, "violations": [{"file": "ch1-test.md", "fig_id": "1-1", "reason": "old"}]}
        )
        code, out = self.run_captions("--diff", baseline)
        self.assertEqual(code, 0, out[-400:])
        self.assertIn("与基线比较", out)
        self.assertIn("已修复", out)

    def test_diff_with_a_corrupt_baseline_exits_two(self):
        path = os.path.join(self.tmp.name, "bad.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        code, out = self.run_captions("--diff", path)
        self.assertEqual(code, 2, out[-400:])

    def test_diff_with_a_missing_baseline_exits_two(self):
        code, out = self.run_captions("--diff", os.path.join(self.tmp.name, "none.json"))
        self.assertEqual(code, 2, out[-400:])

    def test_strict_threshold_fails_on_a_violating_caption(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace("**图 1-1: 展示组件 A 的连接方式**", "**图 1-1: 对比**"))
        code, out = self.run_captions("--threshold", "strict")
        self.assertEqual(code, 1, out[-400:])

    def test_normal_threshold_tolerates_the_fixture(self):
        code, out = self.run_captions("--threshold", "normal")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("TOTAL", out)


if __name__ == "__main__":
    unittest.main()


class CaptionMissingBranchesTest(unittest.TestCase):
    """Record shape, a glob target, an unreadable file, and the two CLI tails."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "captions")

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_a_violation_records_book_relative_paths(self):
        violation = self.mod.Violation(
            file=os.path.join(self.root, "data", "manuscript", "ch1-test.md"),
            line=3,
            fig_id="1-1",
            title="图",
            kind="NO_VERB",
            suggestion="",
        )
        record = violation.to_record()
        self.assertEqual(record["file"], "data/manuscript/ch1-test.md")
        self.assertEqual(record["fig_id"], "1-1")

    def test_a_glob_target_limits_the_scan(self):
        self.write("data/manuscript/ch1-test.md", "# 第1章\n\n**图 1-1: 写入**\n")
        files = self.mod.scan(self.mod.THRESHOLDS["normal"], "data/manuscript/ch1-test.md")
        self.assertEqual({item.fig_id for item in files}, {"1-1"})

    def test_a_glob_matching_directories_and_unreadable_files_is_skipped(self):
        self.write("data/manuscript/figures/note.txt", "x\n")
        broken = self.write("data/manuscript/ch9-test.md", "# 第9章\n")
        real_open = open
        with (
            mock.patch(
                "builtins.open",
                side_effect=lambda *a, **k: (
                    (_ for _ in ()).throw(OSError("denied"))
                    if a and str(a[0]) == broken
                    else real_open(*a, **k)
                ),
            ),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            found = self.mod.scan(self.mod.THRESHOLDS["normal"], "data/manuscript/*")
        self.assertIsInstance(found, list)

    def test_new_violations_are_listed_against_the_baseline(self):
        baseline = os.path.join(self.tmp.name, "base.json")
        with open(baseline, "w", encoding="utf-8") as handle:
            json.dump({"count": 0, "violations": []}, handle)
        self.write("data/manuscript/ch1-test.md", "# 第1章\n\n**图 1-1: 写入**\n")
        args = self.mod._parser().parse_args(["--diff", baseline])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod._diff_report(args, self.mod.scan(self.mod.THRESHOLDS["normal"]))
        self.assertEqual(code, 0)
        self.assertIn("新引入", buffer.getvalue())

    def test_updating_the_baseline_writes_the_keys_and_reports_the_path(self):
        path = os.path.join(self.tmp.name, "captions.json")
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod._baseline, "save", return_value=path) as saved,
            redirect_stdout(buffer),
        ):
            with mock.patch.object(self.mod, "scan", return_value=[]):
                code = self.mod.main(["--update-baseline"])
        self.assertEqual(code, 0)
        saved.assert_called_once()
        self.assertIn("图注基线已更新", buffer.getvalue())
