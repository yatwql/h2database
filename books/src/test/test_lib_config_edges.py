#!/usr/bin/env python3
"""lib._config: the answers a book either does not give or gives badly.

Every case here starts from the fixture book and breaks exactly one declaration,
then asks the reader that has to notice it: a fallback root, a merged policy, a
library that cannot be read, an unusable edition, a source tree that is declared
but not cloned, and a manifest whose version cannot be read.
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:lib", "tier:fast")

_fixture.ensure_tools_path()

_config = importlib.import_module("lib._config")
_book_versions = importlib.import_module("lib._book_versions")


class BookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def book_toml(self) -> pathlib.Path:
        return pathlib.Path(self.root, "data", "book", "book.toml")

    def edit_toml(self, old: str, new: str) -> None:
        text = self.book_toml().read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.book_toml().write_text(text.replace(old, new, 1), encoding="utf-8")

    def append_toml(self, block: str) -> None:
        text = self.book_toml().read_text(encoding="utf-8")
        self.book_toml().write_text(text + block, encoding="utf-8")

    def sources(self, payload: dict) -> None:
        path = pathlib.Path(self.root, "data", "config", "base.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["sources"] = payload
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class RootResolutionTest(unittest.TestCase):
    def test_a_process_that_never_found_a_book_falls_back_to_the_checkout(self):
        with (
            mock.patch.object(_config, "_IMPORT_ROOT", ""),
            mock.patch.object(_config, "find_book_root", return_value=None),
        ):
            self.assertEqual(_config.resolve_book_root(), _config.checkout_root())

    def test_two_policy_files_merge_key_by_key(self):
        merged = _config._merge_policy(
            {"quality": {"a": 1}, "toolchain": {"b": 7}}, {"quality": {"c": 2}}, ""
        )
        self.assertEqual(merged["quality"], {"a": 1, "c": 2})
        self.assertEqual(merged["thresholds"], {"b": 7})


class CandidateBooksTest(BookCase):
    def test_a_book_that_cannot_be_read_still_appears_without_a_library(self):
        library = os.path.join(self.tmp.name, "library")
        root = _fixture.build_book(os.path.join(library, "only"))
        book = pathlib.Path(root, "data", "book", "book.toml")
        book.write_text(
            book.read_text(encoding="utf-8").replace(
                'manuscript = "data/manuscript"', 'manuscript = "../outside"'
            ),
            encoding="utf-8",
        )
        with mock.patch.object(_config, "find_book_root", return_value=""):
            roots = _config.candidate_books(root)
        self.assertEqual(roots, [os.path.abspath(root)])

    def test_a_discovered_start_directory_is_offered_as_well(self):
        other = os.path.join(self.tmp.name, "other")
        _fixture.build_book(other)
        with (
            mock.patch.dict(os.environ, {"BOOKS_DIR": self.tmp.name}),
            mock.patch.object(_config, "find_book_root", return_value=other),
        ):
            roots = _config.candidate_books(self.root)
        self.assertIn(os.path.abspath(other), roots)
        self.assertEqual(len(roots), 2)


class EditionDeclarationTest(BookCase):
    def test_a_default_edition_outside_the_table_is_refused(self):
        self.edit_toml("[book]", 'default_edition = "nope"\n\n[book]')
        self.append_toml('\n[editions]\nmain = "主版本"\n')
        with self.assertRaises(_config.ConfigError) as caught:
            _config.Config(self.root)
        self.assertIn("default_edition", str(caught.exception))

    def test_a_toml_syntax_error_names_the_file(self):
        self.book_toml().write_text("[book\n", encoding="utf-8")
        with self.assertRaises(_config.ConfigError) as caught:
            _config.Config(self.root)
        self.assertIn("invalid TOML", str(caught.exception))

    def test_a_missing_paths_key_is_refused(self):
        self.edit_toml('docs = "docs"\n', "")
        with self.assertRaises(_config.ConfigError) as caught:
            _config.Config(self.root)
        self.assertIn("missing [paths].docs", str(caught.exception))


class TemplatesTest(BookCase):
    def test_a_book_that_opted_into_the_defaults_merges_the_shipped_templates(self):
        self.edit_toml("[book]", "[book]\ndefaults = true")
        os.remove(os.path.join(self.root, "data", "templates", "templates.toml"))
        shipped = pathlib.Path(self.tmp.name, "defaults.json")
        shipped.write_text(json.dumps({"map_intro": "来自默认模板"}), encoding="utf-8")
        with mock.patch.object(_config, "default_path", return_value=str(shipped)):
            merged = _config.Config(self.root).templates()
        self.assertEqual(merged["map_intro"], "来自默认模板")


class SourceTreeTest(BookCase):
    def test_a_book_without_a_source_tree_named_src_main_is_refused(self):
        self.sources({"languages": ["java"]})
        with self.assertRaises(_config.ConfigError) as caught:
            _config.Config(self.root).source_roots()
        self.assertIn("src_main", str(caught.exception))

    def test_the_suffixes_named_for_the_configured_languages_are_used(self):
        self.sources(
            {
                "languages": ["java", "kotlin"],
                "suffixes": {"java": ".java", "kotlin": ".kt"},
            }
        )
        self.assertEqual(_config.Config(self.root).source_suffixes(), [".java", ".kt"])

    def test_a_book_without_a_repository_has_no_clone_target(self):
        self.assertEqual(_config.Config(self.root).clone_target(), "")

    def test_a_declared_repository_that_is_not_cloned_yet_is_refused(self):
        self.sources({"src_main": "src-tree", "repo": "https://github.com/example/h2.git"})
        cfg = _config.Config(self.root)
        with self.assertRaises(_config.ConfigError) as caught:
            cfg.source_tree("src_main")
        self.assertIn("fetch_source.py", str(caught.exception))

    def test_a_cloned_repository_is_the_source_tree(self):
        self.sources({"src_main": "src-tree", "repo": "https://github.com/example/h2.git"})
        cfg = _config.Config(self.root)
        target = cfg.clone_target()
        os.makedirs(target)
        self.assertEqual(cfg.source_tree("main"), os.path.normpath(target))

    def test_an_unknown_source_key_is_refused(self):
        with self.assertRaises(_config.ConfigError) as caught:
            _config.Config(self.root).source_tree("nope")
        self.assertIn("[sources].nope", str(caught.exception))


class ChangeStampTest(BookCase):
    def test_a_missing_git_still_dates_the_tree_from_the_filesystem(self):
        target = os.path.join(self.root, "src", "python")
        os.makedirs(target)
        pathlib.Path(target, "a.py").write_text("x = 1\n", encoding="utf-8")
        with mock.patch.object(_book_versions.subprocess, "run", side_effect=OSError("no git")):
            stamp = _config.Config(self.root).tool_updated()
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}$")

    def test_a_git_stamp_is_used_as_it_stands(self):
        done = _book_versions.subprocess.CompletedProcess(
            args=[], returncode=0, stdout="2025-02-03\n"
        )
        with mock.patch.object(_book_versions.subprocess, "run", return_value=done) as run:
            stamp = _config.Config(self.root).tool_updated()
        self.assertEqual(stamp, "2025-02-03")
        run.assert_called_once()

    def test_a_file_that_cannot_be_stat_ed_contributes_nothing(self):
        target = os.path.join(self.root, "src", "python")
        os.makedirs(target)
        pathlib.Path(target, "a.py").write_text("x = 1\n", encoding="utf-8")
        with (
            mock.patch.object(_book_versions.subprocess, "run", side_effect=OSError("no git")),
            mock.patch.object(_config.os.path, "getmtime", side_effect=OSError("gone")),
        ):
            self.assertEqual(_config.Config(self.root).tool_updated(), "")


class SourceVersionTest(BookCase):
    def manifest(self, rel: str, text: str) -> None:
        path = pathlib.Path(self.root, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_a_manifest_without_a_version_falls_through_to_unknown(self):
        self.manifest("pom.xml", "<project></project>")
        cfg = _config.Config(self.root)
        self.assertEqual(cfg.source_version(), "unknown")

    def test_a_manifest_without_a_version_lets_the_next_one_answer(self):
        self.sources({"src_main": "src-tree"})
        self.manifest("pom.xml", "<project></project>")
        self.manifest("pyproject.toml", '[project]\nversion = "2.5.0"\n')
        self.assertEqual(_config.Config(self.root).source_version(), "2.5.0")

    def test_a_manifest_inside_the_source_root_is_read_without_a_pom_root(self):
        self.sources({"src_main": "src-tree"})
        self.manifest("src-tree/Cargo.toml", '[package]\nversion = "9.9.9"\n')
        self.assertEqual(_config.Config(self.root).source_version(), "9.9.9")

    def test_a_manifest_that_cannot_be_opened_reads_as_no_version(self):
        self.assertEqual(_book_versions._source_version_from(self.root, r"v(\d+)"), "")


if __name__ == "__main__":
    unittest.main()
