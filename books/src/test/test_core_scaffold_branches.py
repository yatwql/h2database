#!/usr/bin/env python3
"""scaffolding a new book: the refusals, the source line, the book it creates."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:core", "tier:fast")

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class ScaffoldBranchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "scaffold")

    def config_file(self, name: str, text: str) -> None:
        with open(os.path.join(self.root, "data", "config", name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def target(self, name: str = "new-book") -> str:
        return os.path.join(self.tmp.name, name)

    def test_a_broken_language_pack_is_refused_by_name(self):
        with open(
            os.path.join(self.root, "data", "language", "zh.json"), "w", encoding="utf-8"
        ) as fh:
            fh.write("{broken")
        with self.assertRaises(SystemExit) as caught:
            self.mod.scaffold(self.target(), "新书", "zh", False)
        self.assertIn("invalid language pack", str(caught.exception))

    def test_a_broken_base_config_is_refused_by_name(self):
        self.config_file("base.json", "{broken")
        with self.assertRaises(SystemExit) as caught:
            self.mod.scaffold(self.target(), "新书", "zh", False)
        self.assertIn("invalid base config", str(caught.exception))

    def test_a_broken_style_config_is_refused_by_name(self):
        self.config_file("style.json", "{broken")
        with self.assertRaises(SystemExit) as caught:
            self.mod.scaffold(self.target(), "新书", "zh", False)
        self.assertIn("invalid style config", str(caught.exception))

    def test_an_unreadable_manuscript_directory_is_refused(self):
        with (
            mock.patch.object(self.mod.os, "listdir", side_effect=OSError("denied")),
            self.assertRaises(SystemExit) as caught,
        ):
            self.mod.scaffold(self.target(), "新书", "zh", True)
        self.assertIn("cannot list", str(caught.exception))

    def test_scaffolding_writes_the_five_documentside_files(self):
        created = self.mod.scaffold(self.target(), "新书", "zh", False)
        for rel in (
            "data/book/book.toml",
            "data/tmpl/templates.toml",
            "data/language/zh.json",
            "data/config/base.json",
            "data/config/style.json",
        ):
            with self.subTest(rel=rel):
                self.assertIn(rel, created)
                self.assertTrue(os.path.isfile(os.path.join(self.target(), rel)))

    def test_scaffolding_twice_keeps_the_first_copy(self):
        self.mod.scaffold(self.target(), "新书", "zh", False)
        panic = os.path.join(self.target(), "data", "book", "book.toml")
        with open(panic, encoding="utf-8") as fh:
            before = fh.read()
        created = self.mod.scaffold(self.target(), "另一本书", "zh", False)
        self.assertEqual(created, [])
        with open(panic, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_a_repository_is_recorded_as_repo_and_a_directory_as_src_main(self):
        book = self.target("target")
        self.mod.scaffold(book, "新书", "zh", False)
        self.assertIn("repo =", self.mod.set_source(book, "https://example.com/x.git"))
        self.assertIn("src_main =", self.mod.set_source(book, "h2/src/main"))
        self.assertEqual(self.mod.set_source(book, "   "), "")
        with open(os.path.join(book, "data", "book", "book.toml"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("https://example.com/x.git", text)
        self.assertIn("src_main", text)

    def test_create_book_lays_out_a_book_the_tools_can_read(self):
        base = os.path.join(self.tmp.name, "library")
        root, created = self.mod.create_book("My New Book", "h2/src/main", base_dir=base)
        self.assertTrue(os.path.isdir(root), created)
        self.assertTrue(os.path.isfile(os.path.join(root, "data", "book", "book.toml")))
        self.assertTrue(any("book.toml" in name for name in created))

    def test_the_entry_point_creates_a_book_and_says_what_is_next(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([self.target("cli-book"), "--title", "命令行新书"])
        out = buffer.getvalue()
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("created", out)
        self.assertIn("bookctl analyze", out)

    def test_the_entry_point_reports_a_directory_that_already_holds_a_book(self):
        target = self.target("twice")
        self.mod.main([target])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([target])
        self.assertEqual(code, 0)
        self.assertIn("nothing created", buffer.getvalue())

    def test_an_english_style_without_captions_gains_none(self):
        with open(os.path.join(self.root, "data", "config", "style.json"), encoding="utf-8") as fh:
            style = json.load(fh)
        style.pop("captions", None)
        self.config_file("style.json", json.dumps(style, ensure_ascii=False))
        produced = self.mod.style_for("en")
        self.assertNotIn("captions", produced)
        self.assertEqual(produced["style_rules"]["terminology"], [])

    def test_a_book_created_without_a_source_records_none(self):
        base = os.path.join(self.tmp.name, "bare-library")
        root, created = self.mod.create_book("Bare Book", base_dir=base)
        self.assertFalse([name for name in created if "=" in name], created)
        with open(os.path.join(root, "data", "book", "book.toml"), encoding="utf-8") as fh:
            self.assertNotIn("[sources]", fh.read())

    def test_the_script_entry_point_scaffolds_a_book(self):
        target = self.target("script-book")
        code, out = _fixture.run_inproc(self.root, "scaffold.py", target, "--title", "脚本新书")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("created", out)
        self.assertTrue(os.path.isfile(os.path.join(target, "data", "book", "book.toml")))


if __name__ == "__main__":
    unittest.main()
