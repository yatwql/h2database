#!/usr/bin/env python3
"""version_consistency: the name and version rules that only fire on drift."""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class VersionConsistencyRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "version_consistency")

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def title(self) -> str:
        return self.mod._config.current().title or "测试之书"

    def test_a_document_without_the_software_name_is_reported(self):
        self.write("docs/managements/plan.md", "# 计划\n\n> 版本：v0.1\n\n没有称号。\n")
        problems = self.mod.software_problems()
        self.assertTrue(any("plan.md" in problem for problem in problems), problems)

    def test_a_document_that_names_one_book_is_reported(self):
        title = self.title()
        self.write("docs/managements/plan.md", f"# 计划\n\n> 版本：v0.1\n\n这本书叫《{title}》。\n")
        problems = self.mod.title_problems()
        self.assertTrue(any("plan.md" in problem for problem in problems), problems)

    def test_a_readme_that_names_one_book_is_reported(self):
        title = self.title()
        self.write("README.md", f"# README\n\n本仓构建《{title}》。\n")
        problems = self.mod.title_problems()
        self.assertTrue(any("README.md" in problem for problem in problems), problems)

    def test_a_cover_whose_version_disagrees_is_reported(self):
        self.write("data/manuscript/cover.md", f"# {self.title()}\n\n版本 v9.9 · 2026-01-01\n")
        problems = self.mod.cover_problems()
        self.assertTrue(any("v9.9" in problem for problem in problems), problems)

    def test_an_artifact_text_is_none_when_it_cannot_be_read(self):
        broken = os.path.join(self.root, "dist", "broken.pdf")
        os.makedirs(os.path.dirname(broken), exist_ok=True)
        with open(broken, "wb") as fh:
            fh.write(b"not a pdf")
        self.assertIsNone(self.mod.artifact_text(broken))

    def test_html_text_is_read_directly(self):
        path = self.write("dist/test-book.html", "<p>正文</p>")
        self.assertIn("正文", self.mod.artifact_text(path) or "")

    def test_json_mode_reports_every_section(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--json"])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 0 if not payload["problems"] else 1)
        for key in ("versions", "problems", "warnings"):
            self.assertIn(key, payload)


class VersionConsistencyExtraBranchesTest(unittest.TestCase):
    """The name rules that fire on source files, display fields and artifacts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "version_consistency")

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def app_names(self) -> tuple[str, str]:
        version = importlib.import_module("lib._version")
        return version.APP_NAME, version.APP_NAME_ZH

    def test_a_source_file_that_spells_the_software_name_is_reported(self):
        name, chinese = self.app_names()
        self.write("docs/managements/plan.md", f"# 计划\n\n{name} 与 {chinese}\n")
        self.write("src/python/bad.py", f"LABEL = {name!r}\n")
        problems = self.mod.software_problems()
        self.assertTrue(any("bad.py" in problem for problem in problems), problems)

    def test_a_display_field_that_drops_the_title_is_reported(self):
        with mock.patch.object(self.mod._config, "project", return_value="另一个书名"):
            problems = self.mod.title_problems()
        self.assertTrue(any("another" in p or "另一个书名" in p for p in problems), problems)

    def test_a_book_without_a_cover_has_nothing_to_check(self):
        with mock.patch.object(
            self.mod._config,
            "manuscript",
            lambda name: os.path.join(self.tmp.name, "missing", name),
        ):
            self.assertEqual(self.mod.cover_problems(), [])

    def test_a_cover_without_a_version_line_is_skipped(self):
        self.write("data/manuscript/cover.md", "# 测试之书\n\n正文\n")
        self.assertEqual(self.mod.cover_problems(), [])

    def test_a_pdf_artifact_is_read_through_the_pdf_reader(self):
        page = mock.Mock()
        page.extract_text.return_value = "封面"
        reader = mock.Mock()
        reader.pages = [page]
        fake = mock.Mock()
        fake.PdfReader.return_value = reader
        path = os.path.join(self.root, "dist", "test-book.pdf")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").close()
        with mock.patch.dict(sys.modules, {"pypdf": fake}):
            self.assertEqual(self.mod.artifact_text(path), "封面")

    def test_a_cover_that_spells_the_software_name_is_reported(self):
        name, _chinese = self.app_names()
        self.write("data/manuscript/cover.md", f"# 测试之书\n\n{name}\n")
        problems = self.mod.book_name_problems()
        self.assertTrue(any("cover.md" in problem for problem in problems), problems)

    def test_an_unreadable_artifact_is_skipped(self):
        path = self.write("dist/test-book.html", "<p>正文</p>")
        with mock.patch.object(self.mod, "artifact_text", return_value=None):
            with mock.patch.object(self.mod._config, "merged_html", lambda: path):
                self.assertEqual(self.mod.book_name_problems(), [])

    def test_a_delivered_artifact_that_carries_the_name_is_reported(self):
        name, _chinese = self.app_names()
        path = self.write("dist/test-book.html", f"<p>{name}</p>")
        with mock.patch.object(self.mod._config, "merged_html", lambda: path):
            problems = self.mod.book_name_problems()
        self.assertTrue(any("test-book.html" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
