#!/usr/bin/env python3
"""Baseline files: the configured path, the edition scope, and the fallback."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:lib", "tier:fast")

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class BaselinePathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        # refresh_config points the process at this book; put the selection back so
        # the next suite does not inherit a directory this test deletes
        previous_env = os.environ.get("BOOK_ROOT")
        previous_cfg = _fixture.load_module(self.root, "make")._config.current()
        if previous_env is None:
            self.addCleanup(os.environ.pop, "BOOK_ROOT", None)
        else:
            self.addCleanup(os.environ.__setitem__, "BOOK_ROOT", previous_env)
        self.addCleanup(lambda: __import__("lib._config", fromlist=["reset"]).reset(previous_cfg))
        _fixture.refresh_config(self.root)
        self.mod = __import__("lib._config", fromlist=["Config"])
        self.baselines = __import__("lib._baseline", fromlist=["path_for"])

    def test_a_configured_name_resolves_through_the_active_book(self):
        name = next(iter(self.mod.BASE_POLICY.get("baselines") or {}))
        path = self.baselines.path_for(name)
        self.assertTrue(path.startswith(os.path.abspath(self.root)))
        self.assertEqual(path, self.mod.current().baseline_path(name))

    def test_an_unconfigured_name_falls_back_beside_the_others(self):
        path = self.baselines.path_for("no-such-gate")
        self.assertTrue(path.endswith("no-such-gate-findings.json"))
        self.assertEqual(os.path.dirname(path), self.mod.baseline_dir())

    def test_the_edition_scopes_the_configured_path(self):
        book_toml = os.path.join(self.root, "data", "book", "book.toml")
        with open(book_toml, encoding="utf-8") as fh:
            original = fh.read()
        with open(book_toml, "w", encoding="utf-8") as fh:
            fh.write('default_edition = "main"\n' + original + '\n[editions]\nmain = "主版本"\n')
        self.mod.reset(self.mod.Config(self.root))
        name = next(iter(self.mod.BASE_POLICY.get("baselines") or {}))
        path = self.baselines.path_for(name)
        self.assertIn(os.path.join("baselines", "main"), path)


class ManuscriptFileOrderTest(unittest.TestCase):
    """The reading order keeps each existing file once."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "_volume")

    def test_a_missing_or_repeated_manuscript_file_is_listed_once(self):
        existing = os.path.join(self.root, "data", "manuscript", "cover.md")
        missing = os.path.join(self.root, "data", "manuscript", "absent.md")
        with (
            mock.patch.object(self.mod._config, "front_matter", lambda: [existing, existing]),
            mock.patch.object(self.mod._config, "chapter_files", lambda **kwargs: []),
            mock.patch.object(self.mod._config, "back_matter", lambda: [missing, existing]),
        ):
            self.assertEqual(self.mod.manuscript_files(), [existing])




class VolumeHeadroomTest(unittest.TestCase):
    """Headroom is blank, not zero, when there is nothing to measure against."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "_volume")

    def baseline(self, body: str) -> str:
        path = os.path.join(self.tmp.name, "volume.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path

    def test_a_broken_baseline_has_no_headroom(self):
        path = self.baseline("{not json")
        with mock.patch.object(self.mod, "baseline_path", lambda: path):
            self.assertIsNone(self.mod.headroom())

    def test_a_baseline_without_lines_has_no_headroom(self):
        path = self.baseline('{"manuscript": {"total": {"lines": 0}}}')
        with mock.patch.object(self.mod, "baseline_path", lambda: path):
            self.assertIsNone(self.mod.headroom())


if __name__ == "__main__":
    unittest.main()
