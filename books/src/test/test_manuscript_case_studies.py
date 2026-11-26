#!/usr/bin/env python3
"""In-process smoke + behaviour tests for every delivery script.

Each script is executed with ``runpy`` against the fixture book, so coverage
counts the real code paths (a subprocess run would not) while staying
deterministic and offline.

Environment-dependent scripts (PDF/EPUB toolchain) run only when their
optional dependencies are importable; otherwise they are skipped by name so the
gap stays visible instead of silently passing.
"""

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:manuscript", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)






class ScriptTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_script(self, script: str, *args: str) -> tuple[int, str]:
        return _fixture.run_inproc(self.root, script, *args)

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def read(self, *parts: str) -> str:
        with open(self.path(*parts), encoding="utf-8") as fh:
            return fh.read()

    def write(self, rel: str, text: str) -> str:
        path = self.path(*rel.split("/"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path


class TestCaseStudyOutline(ScriptTestBase):
    def test_each_scenario_renders(self):
        for scenario in ("select", "commit", "recover"):
            with self.subTest(scenario=scenario):
                code, out = self.run_script("case_studies.py", "--scenario", scenario)
                self.assertEqual(code, 0, out)
                self.assertTrue(out.strip())


class CoverStatsTest(ScriptTestBase):
    """cover.py repeats only what book.toml declares, and counts what it finds."""

    def test_the_cover_repeats_the_counts_and_the_source_references(self):
        self.write(
            "data/manuscript/cover.md",
            "# 旧标题\n\n> 版本 v0.0 · 2020-01-01 · 1 行\n\n副标题。\n\n"
            "全书共 3 章 · 99 幅 ASCII 图 · 120 处源码引用。\n",
        )
        code, out = self.run_script("cover.py")
        self.assertEqual(code, 0, out[-300:])
        cover = self.read("data/manuscript/cover.md")
        self.assertIn("处源码引用", cover)
        self.assertNotIn("120 处源码引用", cover)
        self.assertIn("# 测试之书", cover)

    def test_a_listed_chapter_that_does_not_exist_yet_is_skipped(self):
        os.unlink(self.path("data", "manuscript", "ch2-test.md"))
        code, out = self.run_script("cover.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("1 图", out)

    def test_a_book_without_a_title_or_a_version_keeps_its_cover(self):
        path = self.path("data/book/book.toml")
        text = self.read("data/book/book.toml")
        text = text.replace('title = "测试之书"', 'title = ""')
        text = text.replace('version = "0.1"', 'version = ""')
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        before = self.read("data/manuscript/cover.md").splitlines()
        code, out = self.run_script("cover.py")
        self.assertEqual(code, 0, out[-300:])
        after = self.read("data/manuscript/cover.md").splitlines()
        self.assertEqual(after[0], before[0])
        self.assertEqual(after[1], before[1])




class MissingConfigTest(unittest.TestCase):
    """A book without case studies has no file — that is not a crash."""

    def test_load_scenarios_returns_empty_when_the_file_is_absent(self):
        case_studies = importlib.import_module("case_studies")

        with mock.patch.object(
            case_studies, "case_study_config", lambda: os.path.join(self.tmp, "absent.toml")
        ):
            self.assertEqual(case_studies.load_scenarios(), {})

    def test_headers_come_from_the_book_file_and_are_empty_without_one(self):
        case_studies = importlib.import_module("case_studies")
        target = os.path.join(self.tmp, "case-studies.toml")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write('[headers.select]\nheading = "## A.1 示例"\nopening = "开篇。"\n')
        with mock.patch.object(case_studies, "case_study_config", lambda: target):
            self.assertEqual(case_studies.scenario_headers()["select"]["heading"], "## A.1 示例")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("[scenarios.select]\n")
            self.assertEqual(case_studies.scenario_headers(), {})

    def test_headers_of_a_broken_file_are_ignored(self):
        case_studies = importlib.import_module("case_studies")
        target = os.path.join(self.tmp, "broken.toml")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("{not toml")
        with mock.patch.object(case_studies, "case_study_config", lambda: target):
            self.assertEqual(case_studies.scenario_headers(), {})

    def test_the_books_questions_replace_the_neutral_default(self):
        case_studies = importlib.import_module("case_studies")
        target = os.path.join(self.tmp, "case-studies.toml")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write('[headers.select]\nheading = "## A.1 示例"\n'
                     'questions = ["这道题属于本书"]\n'
                     '[scenarios.select]\n[[scenarios.select.steps]]\n'
                     'component = "入口"\nanchor = "§1.1"\ndecision = "进入"\n')
        with mock.patch.object(case_studies, "case_study_config", lambda: target):
            rendered = case_studies.render("select")
        self.assertIn("1. 这道题属于本书", rendered)
        self.assertNotIn(case_studies.DEFAULT_QUESTIONS[0], rendered)

    def test_a_book_without_questions_gets_the_neutral_ones(self):
        case_studies = importlib.import_module("case_studies")
        target = os.path.join(self.tmp, "case-studies.toml")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write('[headers.select]\nheading = "## A.1 示例"\n'
                     '[scenarios.select]\n[[scenarios.select.steps]]\n'
                     'component = "入口"\nanchor = "§1.1"\ndecision = "进入"\n')
        with mock.patch.object(case_studies, "case_study_config", lambda: target):
            rendered = case_studies.render("select")
        self.assertIn(case_studies.DEFAULT_QUESTIONS[0], rendered)
        self.assertIn("1. ", rendered)

    def test_a_broken_file_stops_the_scenario_loader(self):
        case_studies = importlib.import_module("case_studies")
        target = os.path.join(self.tmp, "broken.toml")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("{not toml")
        with mock.patch.object(case_studies, "case_study_config", lambda: target):
            with self.assertRaises(SystemExit) as caught:
                case_studies.load_scenarios()
        self.assertIn("invalid TOML", str(caught.exception))

    def test_an_unknown_scenario_is_rejected(self):
        case_studies = importlib.import_module("case_studies")
        with mock.patch.object(case_studies, "scenarios", lambda: {"select": []}):
            with self.assertRaises(ValueError) as caught:
                case_studies.render("nope")
        self.assertIn("unknown scenario 'nope'", str(caught.exception))

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)


if __name__ == "__main__":
    unittest.main()
