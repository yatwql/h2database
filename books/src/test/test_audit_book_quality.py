#!/usr/bin/env python3
"""Book quality gate: the manuscript metrics and the thresholds they feed."""

from __future__ import annotations

import importlib
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()


def ladder_sections() -> str:
    """The four information-ladder headings every body chapter must carry."""
    stages = ("模块版图", "核心类型", "关键 API 与源码坐标", "阅读路径")
    return "".join(f"## 1.{i} {stage}\n\n详见第2章。\n" for i, stage in enumerate(stages, 1))


class BookQualityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        # refresh_config points the process at this book; put it back afterwards
        previous_env = os.environ.get("BOOK_ROOT")
        previous = importlib.import_module("lib._config").current()
        self.addCleanup(importlib.import_module("lib._config").reset, previous)
        if previous_env is None:
            self.addCleanup(os.environ.pop, "BOOK_ROOT", None)
        else:
            self.addCleanup(os.environ.__setitem__, "BOOK_ROOT", previous_env)
        _fixture.refresh_config(self.root)

    def gate(self):
        return _fixture.load_module(self.root, "book_quality")

    def rewrite_book_toml(self, files: str) -> None:
        """Replace the `[chapters] files` list of the fixture's book.toml."""
        path = os.path.join(self.root, "data", "book", "book.toml")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        start = text.index("files = [")
        end = text.index("]", start) + 1
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text[:start] + f"files = {files}" + text[end:])

    def append_to_chapter(self, name: str, text: str) -> None:
        with open(os.path.join(self.root, "data", "manuscript", name), "a", encoding="utf-8") as fh:
            fh.write(text)

    def test_a_chapter_listed_but_absent_from_disk_is_skipped(self):
        self.rewrite_book_toml('["cover.md", "ch1-test.md", "ch2-test.md", "ch3-absent.md"]')
        module = self.gate()
        report = module.measure()
        self.assertNotIn("ch3-absent.md", report["per_file"])
        self.assertEqual(report["totals"]["files"], 2)

    def test_a_book_without_body_chapters_passes_and_says_so(self):
        self.rewrite_book_toml('["cover.md"]')
        module = self.gate()
        self.assertEqual(module.failures(module.measure()), [])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = module.main([])
        self.assertEqual(code, 0)
        self.assertIn("全部达标", buffer.getvalue())

    def test_a_manuscript_that_meets_every_threshold_passes(self):
        for name in ("ch1-test.md", "ch2-test.md"):
            self.append_to_chapter(name, ladder_sections())
        module = self.gate()
        self.assertEqual(module.failures(module.measure()), [])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = module.main([])
        self.assertEqual(code, 0, buffer.getvalue()[-300:])

    def test_a_missing_ladder_layer_fails_the_gate(self):
        module = self.gate()
        problems = module.failures(module.measure())
        self.assertIn("chapter_ladder", " ".join(problems))

    def test_warn_only_turns_a_failing_gate_green(self):
        module = self.gate()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = module.main(["--warn-only"])
        self.assertEqual(code, 0)
        self.assertIn("未达标", buffer.getvalue())

    def test_the_script_entrypoint_reports_through_the_error_wrapper(self):
        code, output = _fixture.run_inproc(self.root, "book_quality.py")
        self.assertEqual(code, 1, output[-300:])
        self.assertIn("未达标", output)


if __name__ == "__main__":
    unittest.main()
