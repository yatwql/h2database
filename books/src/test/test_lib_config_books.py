#!/usr/bin/env python3
"""The configuration is one object per book, not one process-wide singleton.

These cases are the contract the multi-book layout relies on: two books in the
same process never see each other's paths, and the module-level helpers follow
whichever book is active for the duration of a ``with use(...)`` block.
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:lib", "tier:fast")

_fixture.ensure_tools_path()
_config = importlib.import_module("lib._config")


def make_book(root: str, title: str, merged: str, state: str) -> None:
    """Write the smallest book that Config can load."""
    book_dir = os.path.join(root, "data", "book")
    os.makedirs(book_dir, exist_ok=True)
    os.makedirs(os.path.join(root, "data", "config"), exist_ok=True)
    with open(os.path.join(book_dir, "book.toml"), "w", encoding="utf-8") as fh:
        fh.write(f'''[book]
title = "{title}"
version = "1.0"
merged_name = "{merged}"

[paths]
manuscript = "data/manuscript"
dist = "dist"
docs = "docs"
tmp = "data/tmp"
state = "{state}"

[chapters]
files = ["ch1.md"]

[chapters.packages]
"ch1.md" = ["org.example"]
''')
    with open(os.path.join(root, "data", "config", "base.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "paths": {},
                "sources": {
                    "src_main": "src-tree",
                    "languages": ["java"],
                    "suffixes": {"java": ".java"},
                },
            },
            fh,
        )
    with open(os.path.join(root, "data", "config", "style.json"), "w", encoding="utf-8") as fh:
        json.dump({"thresholds": {}}, fh)


class TwoBooksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.one = os.path.join(self.tmp, "one")
        self.two = os.path.join(self.tmp, "two")
        for root, title, merged, state in (
            (self.one, "第一本", "alpha", "data/state"),
            (self.two, "第二本", "beta", "data/state-b"),
        ):
            make_book(root, title, merged, state)

    def test_two_books_keep_their_own_values(self):
        first, second = _config.Config(self.one), _config.Config(self.two)
        self.assertEqual(first.title, "第一本")
        self.assertEqual(second.title, "第二本")
        self.assertEqual(first.state_dir(), os.path.join(self.one, "data", "state"))
        self.assertEqual(second.state_dir(), os.path.join(self.two, "data/state-b"))
        self.assertTrue(first.merged_md().endswith("alpha.md"))
        self.assertTrue(second.merged_md().endswith("beta.md"))

    def test_a_book_reads_only_its_own_files(self):
        first = _config.Config(self.one)
        self.assertEqual(first.chapter_names(), ["ch1.md"])
        self.assertEqual(
            first.manuscript("ch1.md"), os.path.join(self.one, "data", "manuscript", "ch1.md")
        )
        self.assertEqual(first.chapter_packages(), {"ch1.md": ["org.example"]})

    def test_module_helpers_follow_the_active_book(self):
        second = _config.Config(self.two)
        with _config.use(second) as active:
            self.assertIs(active, second)
            self.assertEqual(_config.BOOK_ROOT, self.two)
            self.assertEqual(_config.TITLE, "第二本")
            self.assertEqual(
                _config.state_path("outline.json"),
                os.path.join(self.two, "data/state-b", "outline.json"),
            )
            self.assertEqual(_config.chapter_names(), ["ch1.md"])
        self.assertEqual(_config.BOOK_ROOT, _config.current().root)
        self.assertNotEqual(_config.BOOK_ROOT, self.two)

    def test_the_previous_book_returns_even_when_the_block_raises(self):
        before = _config.current()
        with self.assertRaises(RuntimeError), _config.use(_config.Config(self.two)):
            raise RuntimeError("boom")
        self.assertIs(_config.current(), before)

    def test_nested_blocks_restore_in_order(self):
        one, two = _config.Config(self.one), _config.Config(self.two)
        with _config.use(one):
            with _config.use(two):
                self.assertEqual(_config.TITLE, "第二本")
            self.assertEqual(_config.TITLE, "第一本")

    def test_an_unknown_module_attribute_still_fails(self):
        name = "NO_SUCH_SETTING"
        self.assertNotIn(name, dir(_config))
        with self.assertRaises(AttributeError):
            getattr(_config, name)

    def test_a_missing_book_file_is_a_config_error(self):
        with self.assertRaises(_config.ConfigError):
            _config.Config(os.path.join(self.tmp, "nowhere"))

    def test_an_explicit_book_beats_the_environment(self):
        with _config.use(_config.Config(self.one)):
            os.environ["BOOK_ROOT"] = self.two
            try:
                self.assertEqual(_config.resolve_book_root(self.one), self.one)
                self.assertEqual(_config.resolve_book_root(None), os.path.abspath(self.two))
            finally:
                os.environ.pop("BOOK_ROOT", None)

    def test_looking_up_finds_the_nearest_book(self):
        nested = os.path.join(self.one, "data", "manuscript", "ch1")
        os.makedirs(nested, exist_ok=True)
        self.assertEqual(_config.find_book_root(nested), self.one)

    def test_where_there_is_no_book_the_lookup_returns_nothing(self):
        self.assertEqual(_config.find_book_root(self.tmp), "")

    def test_candidates_include_the_active_book_and_its_siblings(self):
        roots = _config.candidate_books(self.one, start=self.tmp)
        self.assertEqual(roots[0], self.one)
        self.assertIn(os.path.abspath(self.two), roots)

    def test_an_explicit_library_replaces_the_active_books_parent(self):
        elsewhere = os.path.join(self.tmp, "elsewhere")
        third = os.path.join(elsewhere, "three")
        make_book(third, "第三本", "gamma", "data/state")
        roots = _config.candidate_books(self.one, start=self.tmp, library=elsewhere)
        self.assertEqual(roots, [self.one, os.path.abspath(third)])

    def test_a_library_that_cannot_be_listed_still_yields_itself(self):
        self.assertEqual(_config.books_in(os.path.join(self.tmp, "nope")), [])
        self.assertEqual(_config.books_in(self.one), [self.one])

    def test_an_invalid_policy_file_names_the_file(self):
        path = os.path.join(self.one, "data", "config", "broken.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{broken")
        with self.assertRaises(_config.ConfigError) as caught:
            _config._read_policy(path)
        self.assertIn("invalid JSON", str(caught.exception))

    def test_without_split_policies_the_legacy_file_is_used(self):
        legacy = os.path.join(self.tmp, "config.json")
        with open(legacy, "w", encoding="utf-8") as fh:
            json.dump({"thresholds": {"custom": 1}}, fh)
        merged = _config._merge_policy({}, {}, legacy)
        self.assertEqual(merged["thresholds"]["custom"], 1)

    def test_toolchain_budgets_are_reachable_as_thresholds(self):
        merged = _config._merge_policy({"toolchain": {"coverage_fail_under": 88}}, {}, "")
        self.assertEqual(merged["thresholds"]["coverage_fail_under"], 88)

    def test_candidates_survive_a_parent_that_cannot_be_listed(self):
        with mock.patch.object(_config.os, "listdir", side_effect=OSError("denied")):
            roots = _config.candidate_books(self.one)
        self.assertIn(self.one, roots)

    def test_a_path_that_escapes_the_book_root_is_refused(self):
        book = os.path.join(self.one, "data", "book", "book.toml")
        text = pathlib.Path(book).read_text(encoding="utf-8")
        pathlib.Path(book).write_text(
            text.replace('manuscript = "data/manuscript"', 'manuscript = "../outside"'),
            encoding="utf-8",
        )
        with self.assertRaises(_config.ConfigError):
            _config.Config(self.one)

    def declare_editions(self, root: str, editions: str, default: str = "") -> None:
        """Add an [editions] table to a fixture book."""
        path = os.path.join(root, "data", "book", "book.toml")
        text = pathlib.Path(path).read_text(encoding="utf-8")
        block = editions if not default else f'default_edition = "{default}"\n{editions}'
        pathlib.Path(path).write_text(text + "\n" + block, encoding="utf-8")

    def test_a_book_without_editions_keeps_todays_layout(self):
        cfg = _config.Config(self.one)
        self.assertEqual(cfg.edition, "")
        self.assertTrue(cfg.manuscript_dir.endswith(os.path.join("data", "manuscript")))
        self.assertTrue(cfg.state_dir().endswith(os.path.join("data", "state")))
        self.assertTrue(cfg.merged_md().endswith("alpha.md"))

    def test_a_single_edition_is_selected_implicitly(self):
        self.declare_editions(self.one, '[editions]\nmain = "主版本"\n')
        cfg = _config.Config(self.one)
        self.assertEqual(cfg.edition, "main")
        self.assertTrue(cfg.manuscript_dir.endswith(os.path.join("manuscript", "main")))
        self.assertTrue(cfg.state_dir().endswith(os.path.join("state", "main")))
        self.assertTrue(cfg.baseline_dir().endswith(os.path.join("baselines", "main")))
        self.assertTrue(cfg.merged_md().endswith("alpha-main.md"))

    def test_several_editions_require_a_default(self):
        self.declare_editions(self.one, '[editions]\nmain = "主版本"\nabridged = "删节版"\n')
        with self.assertRaises(_config.ConfigError):
            _config.Config(self.one)
        self.assertEqual(_config.Config(self.one, "abridged").edition, "abridged")

    def test_an_undeclared_edition_is_refused(self):
        self.declare_editions(self.one, '[editions]\nmain = "主版本"\n')
        with self.assertRaises(_config.ConfigError):
            _config.Config(self.one, "nope")

    def test_the_environment_selects_the_edition(self):
        self.declare_editions(self.one, '[editions]\nmain = "主版本"\n')
        os.environ["BOOK_EDITION"] = "main"
        try:
            self.assertEqual(_config.Config(self.one).edition, "main")
        finally:
            os.environ.pop("BOOK_EDITION", None)

    def declare_sources(self, root: str, block: str) -> None:
        """Replace [sources] in the fixture base.json."""
        path = os.path.join(root, "data", "config", "base.json")
        payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        payload["sources"] = json.loads(block)
        pathlib.Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_a_single_source_tree_is_labelled_main(self):
        cfg = _config.Config(self.one)
        self.assertEqual([root["label"] for root in cfg.source_roots()], ["main"])
        self.assertTrue(cfg.source_tree("src_main").endswith("src-tree"))

    def test_several_roots_are_listed_and_looked_up_by_label(self):
        self.declare_sources(
            self.one,
            json.dumps({"roots": [{"label": "h2", "path": "a"}, {"label": "client", "path": "b"}]}),
        )
        cfg = _config.Config(self.one)
        self.assertEqual([root["label"] for root in cfg.source_roots()], ["h2", "client"])
        self.assertTrue(cfg.source_tree("src_main").endswith("a"))
        self.assertTrue(cfg.source_tree("client").endswith("b"))

    def test_a_duplicate_root_label_is_refused(self):
        self.declare_sources(
            self.one,
            json.dumps({"roots": [{"label": "h2", "path": "a"}, {"label": "h2", "path": "b"}]}),
        )
        with self.assertRaises(_config.ConfigError):
            _config.Config(self.one).source_roots()

    def test_a_root_without_a_path_is_refused(self):
        self.declare_sources(self.one, json.dumps({"roots": [{"label": "h2"}]}))
        with self.assertRaises(_config.ConfigError):
            _config.Config(self.one).source_roots()

    def test_library_paths_follow_the_active_book(self):
        baseline = importlib.import_module("lib._baseline")
        llm = importlib.import_module("lib._llm")
        for module, getter in (
            (baseline, baseline.baseline_dir),
            (llm, llm.provider_path),
            (llm, llm.settings_path),
        ):
            inner = module._config  # the instance this module actually holds
            with inner.use(inner.Config(self.two)):
                self.assertTrue(getter().startswith(self.two), getter.__name__)

    def test_the_library_defaults_to_the_parent_directory(self):
        self.assertEqual(_config.Config(self.one).library_dir(), self.tmp)

    def test_a_declared_library_changes_the_candidates(self):
        library = os.path.join(self.tmp, "library")
        os.makedirs(library, exist_ok=True)
        for name in ("left", "right"):
            make_book(os.path.join(library, name), name, name, "data/state")
        book = os.path.join(library, "left")
        path = os.path.join(book, "data", "book", "book.toml")
        text = pathlib.Path(path).read_text(encoding="utf-8")
        pathlib.Path(path).write_text(
            text.replace("[paths]", '[paths]\nlibrary = ".."'), encoding="utf-8"
        )
        self.assertEqual(_config.Config(book).library_dir(), library)
        roots = _config.candidate_books(book, start=self.tmp)
        self.assertEqual(sorted(os.path.basename(root) for root in roots), ["left", "right"])

    def enable_defaults(self, root: str) -> None:
        path = os.path.join(root, "data", "book", "book.toml")
        text = pathlib.Path(path).read_text(encoding="utf-8")
        pathlib.Path(path).write_text(
            text.replace("[book]", "[book]\ndefaults = true", 1), encoding="utf-8"
        )

    def test_a_book_without_the_flag_keeps_an_empty_policy(self):
        os.remove(os.path.join(self.one, "data", "config", "base.json"))
        cfg = _config.Config(self.one)
        self.assertFalse(cfg.use_defaults)
        self.assertEqual(cfg.policy.get("thresholds"), {})
        self.assertEqual(cfg.language().get("sections") or {}, {})

    def test_a_book_that_opts_in_gets_the_packaged_defaults(self):
        os.remove(os.path.join(self.one, "data", "config", "base.json"))
        self.enable_defaults(self.one)
        cfg = _config.Config(self.one)
        self.assertTrue(cfg.use_defaults)
        self.assertTrue(cfg.policy.get("sources"))
        self.assertTrue(cfg.language().get("sections"))

    def test_the_books_own_values_win_over_the_defaults(self):
        self.enable_defaults(self.one)
        path = os.path.join(self.one, "data", "config", "style.json")
        pathlib.Path(path).write_text(
            json.dumps({"thresholds": {"exercises_min": 3}}), encoding="utf-8"
        )
        cfg = _config.Config(self.one)
        self.assertEqual(cfg.thresholds.get("exercises_min"), 3)
        self.assertTrue(len(cfg.thresholds) > 1)  # the rest still comes from defaults

    def test_the_default_book_matches_its_module_attributes(self):
        active = _config.current()
        self.assertEqual(_config.BOOK_ROOT, active.root)
        self.assertEqual(_config.MANUSCRIPT_DIR, active.manuscript_dir)
        self.assertEqual(_config.THRESHOLDS, active.thresholds)
        self.assertEqual(_config.chapter_names(), active.chapter_names())


if __name__ == "__main__":
    unittest.main()


class ConfigFallbackTest(unittest.TestCase):
    """The paths a book takes when its files are missing, odd or unwritable."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def config(self):
        return _config.Config(self.root)

    def test_an_unwritable_cache_falls_back_to_scratch(self):
        book = self.config()
        with mock.patch.object(_config.os, "makedirs", side_effect=OSError("read-only")):
            self.assertEqual(book.cache_dir(), book.tmp_dir())

    def test_a_missing_template_file_falls_back_to_the_style_policy(self):
        style = pathlib.Path(self.root, "data", "config", "style.json")
        payload = json.loads(style.read_text(encoding="utf-8"))
        payload["generation"]["templates"] = {"map_intro": "来自样式表的旧书模板 {x}"}
        style.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.remove(os.path.join(self.root, "data", "tmpl", "templates.toml"))
        self.assertEqual(self.config().templates(), {"map_intro": "来自样式表的旧书模板 {x}"})

    def test_a_broken_template_file_is_a_config_error(self):
        path = pathlib.Path(self.root, "data", "tmpl", "templates.toml")
        path.write_text("not = [valid", encoding="utf-8")
        with self.assertRaises(_config.ConfigError):
            self.config().templates()

    def test_an_empty_glob_pattern_lists_nothing(self):
        book = self.config()
        with mock.patch.object(book, "chapters_spec", return_value={}):
            self.assertEqual(book._glob_matter("front_matter"), [])

    def test_a_source_root_that_is_not_an_object_is_a_config_error(self):
        path = pathlib.Path(self.root, "data", "config", "base.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("sources", {})["roots"] = ["not-an-object"]
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(_config.ConfigError):
            self.config().source_roots()
