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

SLOW = os.environ.get("BOOK_SLOW") == "1"
HAS_PYPDF = importlib.util.find_spec("pypdf") is not None
HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
HAS_PANDOC = bool(__import__("shutil").which("pandoc"))

BUILD_SCRIPTS = ["cover.py", "merge.py", "to_html.py"]

ALL_SCRIPTS = [
    "cover.py",
    "merge.py",
    "to_html.py",
    "pdf_toc_links.py",
    "to_epub.py",
    "pdf_from_html.py",
    "structure.py",
]

AUDIT_SCRIPTS = [
    "links.py",
    "diagrams.py",
    "captions.py",
    "figures.py",
    "crossrefs.py",
    "exercises.py",
    "figure_clusters.py",
    "index_xrefs.py",
    "smart.py",
    "balance.py",
    "style.py",
    "readability.py",
    "source_refs.py",
    "glossary.py",
    "index.py",
]


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


if __name__ == "__main__":
    unittest.main()


class MissingConfigTest(unittest.TestCase):
    """A book without case studies has no file — that is not a crash."""

    def test_load_scenarios_returns_empty_when_the_file_is_absent(self):
        case_studies = importlib.import_module("case_studies")

        with mock.patch.object(
            case_studies, "case_study_config", lambda: os.path.join(self.tmp, "absent.toml")
        ):
            self.assertEqual(case_studies.load_scenarios(), {})

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
