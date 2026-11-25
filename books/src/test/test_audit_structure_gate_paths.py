#!/usr/bin/env python3
"""structure.py: the report paths of the advisory sub-checks.

Each sub-check wraps a tool the book may not have installed. What it prints in
that case — and what it prints when the tool answers with findings — is the part
a healthy build never reaches, so it is driven here with a mutated book and a
stand-in for the tool.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import types
import unittest
from unittest import mock

import _fixture

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()


class GateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def gate(self, *args):
        return _fixture.run_inproc(self.root, "structure.py", *args)

    def manuscript(self, *parts: str) -> str:
        return os.path.join(self.root, "data", "manuscript", *parts)

    def append(self, path: str, text: str) -> None:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)


class ChapterNumberTest(unittest.TestCase):
    """The chapter set the per-chapter checks follow."""

    @classmethod
    def setUpClass(cls):
        cls.structure = _fixture.load_module(BOOK_ROOT, "structure")

    def test_coverage_entries_that_are_not_chapters_do_not_add_numbers(self):
        with mock.patch.object(
            self.structure._config,
            "chapter_coverage",
            return_value={"ch1-test.md": [1], "cover.md": [0]},
        ):
            self.assertEqual(self.structure.chapter_numbers(), [1])

    def test_without_coverage_the_reading_order_supplies_the_numbers(self):
        with (
            mock.patch.object(self.structure._config, "chapter_coverage", return_value={}),
            mock.patch.object(
                self.structure._config,
                "chapter_numbering",
                return_value={"cover.md": [0], "ch3-test.md": [3]},
            ),
        ):
            self.assertEqual(self.structure.chapter_numbers(), [3])


class CssCheckReportTest(GateCase):
    def renderer(self, fallback):
        """read_text_raw that answers for the renderer only."""

        def read(path):
            if str(path).endswith(("to_html.py", "html_shell.py")):
                return "" if fallback is None else fallback(path)
            return real_read(path)

        real_read = self.structure_fsutil().read_text_raw
        return read

    @staticmethod
    def structure_fsutil():
        return __import__("lib._fsutil", fromlist=["read_text_raw"])

    def test_a_renderer_without_the_hooks_names_each_missing_one(self):
        with mock.patch.object(
            self.structure_fsutil(), "read_text_raw", side_effect=self.renderer(None)
        ):
            code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("[WARN]  Missing: h1 decorator (h1::before)", out)
        self.assertNotIn("All 9 CSS features present", out)

    def test_an_absent_renderer_is_a_skipped_check_not_a_crash(self):
        def missing(_path):
            raise FileNotFoundError("no renderer")

        with mock.patch.object(
            self.structure_fsutil(), "read_text_raw", side_effect=self.renderer(missing)
        ):
            code, out = self.gate()
        self.assertIn("CSS check skipped (to_html.py not found)", out)
        self.assertNotIn("Traceback", out)


class BuilderScriptReportTest(GateCase):
    def test_a_broken_builder_and_a_missing_one_are_reported_apart(self):
        broken = os.path.join(self.root, "data", "manuscript", "glossary.py")
        with open(broken, "w", encoding="utf-8") as handle:
            handle.write("def broken(:\n")
        real_exists = os.path.exists
        scripts = os.path.join(_fixture.TOOLS_DIR, "manuscript")
        hidden = {os.path.join(scripts, "glossary.py"), os.path.join(scripts, "index.py")}

        def exists(path):
            return False if str(path) in hidden else real_exists(path)

        with mock.patch.object(os.path, "exists", side_effect=exists):
            code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("FAIL:", out)
        self.assertIn("[WARN]  index.py not found", out)


class GlossaryReportTest(GateCase):
    def test_an_entry_without_a_chapter_reference_is_named(self):
        self.append(
            self.manuscript("back", "glossary.md"),
            "\n## Z\n\n- **Zeta**: 只是一句解释，没有章节引用。\n",
        )
        code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("MISSING CHAPTER REF: Zeta", out)

    def test_a_missing_glossary_file_fails_the_check(self):
        os.remove(self.manuscript("back", "glossary.md"))
        code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("Glossary file not found", out)


class StyleReportTest(GateCase):
    def style_run(self, stdout: str):
        real_run = subprocess.run

        def run(command, **kwargs):
            if any(str(part).endswith("style.py") for part in command):
                return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")
            return real_run(command, **kwargs)

        return run

    def test_the_warning_count_is_read_off_the_style_report(self):
        report = "3 style warnings — review suggested\n[SEQ] 重复句\n[LONG] 超长行\n"
        with mock.patch.object(subprocess, "run", side_effect=self.style_run(report)):
            _code, out = self.gate()
        self.assertIn("[WARN]  3 style warnings", out)
        self.assertIn("[SEQ] 重复句", out)
        self.assertNotIn("    [LONG] 超长行", out)

    def test_a_spotless_style_report_says_so(self):
        with mock.patch.object(subprocess, "run", side_effect=self.style_run("0 style warnings\n")):
            _code, out = self.gate()
        self.assertIn("OK: No style issues (0 warnings)", out)

    def test_a_style_tool_that_cannot_run_is_reported_as_skipped(self):
        real_run = subprocess.run

        def run(command, **kwargs):
            if any(str(part).endswith("style.py") for part in command):
                raise OSError("cannot execute")
            return real_run(command, **kwargs)

        with mock.patch.object(subprocess, "run", side_effect=run):
            _code, out = self.gate()
        self.assertIn("Style check skipped: cannot execute", out)


if __name__ == "__main__":
    unittest.main()
