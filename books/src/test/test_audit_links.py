#!/usr/bin/env python3
"""End-to-end tests: run the delivery scripts against a fixture book.

Each test materialises a miniature book (book.toml + manuscript/ + dist/) in a
temporary directory, points BOOK_ROOT at it, and asserts the script's real
behaviour. This is what catches path drift, config wiring mistakes and
regressions in the audits — the class of bug unit tests cannot see.
"""

import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def dist(self, name: str) -> str:
        return os.path.join(self.root, "dist", name)

    def read(self, path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class TestLinkResolution(FixtureTest):
    """The resolver and the file selection behind the audit (in-process)."""

    def manuscript(self, *parts: str) -> str:
        return os.path.join(self.root, "data", "manuscript", *parts)

    def test_a_target_that_starts_with_a_slash_is_anchored_at_the_manuscript_root(self):
        links = _fixture.load_module(self.root, "links")
        resolved = links._resolve(self.manuscript("ch1-test.md"), "/ch2-test.md")
        self.assertEqual(resolved, os.path.normpath(self.manuscript("ch2-test.md")))

    def test_a_pattern_selects_the_files_to_audit(self):
        links = _fixture.load_module(self.root, "links")
        self.assertEqual(
            [os.path.basename(p) for p in links.target_files("ch2*.md")], ["ch2-test.md"]
        )

    def test_a_file_that_is_not_markdown_is_out_of_scope(self):
        with open(self.manuscript("notes.txt"), "w", encoding="utf-8") as fh:
            fh.write("[坏链接](nope.md)\n")
        links = _fixture.load_module(self.root, "links")
        self.assertEqual(links.scan("*"), [])

    def test_an_anchor_that_a_heading_provides_is_accepted(self):
        with open(self.manuscript("ch2-test.md"), "a", encoding="utf-8") as fh:
            fh.write("\n## 附表\n")
        with open(self.manuscript("ch1-test.md"), "a", encoding="utf-8") as fh:
            fh.write("\n[附表](ch2-test.md#附表)\n")
        links = _fixture.load_module(self.root, "links")
        self.assertEqual(links.scan(), [])

    def test_the_slug_cache_is_reused_across_files(self):
        with open(self.manuscript("ch2-test.md"), "a", encoding="utf-8") as fh:
            fh.write("\n## 附表\n")
        for name in ("ch1-test.md", "ch1-backlink.md"):
            with open(self.manuscript(name), "a", encoding="utf-8") as fh:
                fh.write("\n[附表](ch2-test.md#附表)\n")
        links = _fixture.load_module(self.root, "links")
        cache: dict[str, set[str]] = {}
        for name in ("ch1-test.md", "ch1-backlink.md"):
            self.assertEqual(links.audit_file(self.manuscript(name), cache), [], name)
        self.assertEqual(len(cache), 1)


class TestLinkAudit(FixtureTest):
    def test_clean_fixture_passes(self):
        result = _fixture.run(self.root, "links.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_broken_link_fails(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n[坏的](nope.md)\n")
        result = _fixture.run(self.root, "links.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("BROKEN_FILE", result.stdout)

    def test_broken_anchor_fails(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n[坏的](back/glossary.md#不存在)\n")
        result = _fixture.run(self.root, "links.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("BROKEN_ANCHOR", result.stdout)


if __name__ == "__main__":
    unittest.main()
