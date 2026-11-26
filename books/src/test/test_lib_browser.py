#!/usr/bin/env python3
"""Browser launches: inside the book's tmp directory, and without core dumps."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:lib", "tier:fast")

_fixture.ensure_tools_path()


class BrowserLaunchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.browser = _fixture.load_module(self.root, "_browser")

    def fake_playwright(self, seen: dict):
        def launch(**kwargs):
            seen.update(kwargs)
            return "browser"

        return mock.Mock(chromium=mock.Mock(launch=launch))

    def test_the_browser_scratch_space_is_the_books_tmp_directory(self):
        # Playwright's launch() takes neither `cwd` nor `preexec_fn`: the directory
        # comes from TMPDIR in the child's environment instead.
        seen: dict = {}
        self.assertEqual(self.browser.launch(self.fake_playwright(seen)), "browser")
        tmp = self.browser._config.tmp_dir()
        self.assertEqual(seen["env"]["TMPDIR"], tmp)
        self.assertTrue(os.path.isdir(tmp))
        self.assertNotIn("cwd", seen)
        self.assertTrue(seen["headless"])
        self.assertIn("--no-sandbox", seen["args"])

    def test_the_core_limit_is_zeroed_before_the_browser_starts(self):
        seen: dict = {}
        with mock.patch.object(self.browser, "_no_core_dumps") as guard:
            self.browser.launch(self.fake_playwright(seen))
        guard.assert_called_once_with()

    def test_a_missing_resource_module_does_not_break_the_launch(self):
        with mock.patch.dict("sys.modules", {"resource": None}):
            self.assertIsNone(self.browser._no_core_dumps())

    def test_a_read_only_checkout_still_launches_the_browser(self):
        seen: dict = {}
        with mock.patch.object(self.browser.os, "makedirs", side_effect=OSError("denied")):
            self.browser.launch(self.fake_playwright(seen))
        self.assertNotIn("TMPDIR", seen["env"])
        self.assertEqual(seen["args"], list(self.browser.LAUNCH_ARGS))

    def test_a_caller_supplied_environment_is_kept(self):
        seen: dict = {}
        self.browser.launch(self.fake_playwright(seen), env={"PATH": "/bin", "LANG": "C"})
        self.assertEqual(seen["env"]["LANG"], "C")
        self.assertEqual(seen["env"]["TMPDIR"], self.browser._config.tmp_dir())

    def test_callers_can_add_arguments_without_repeating_the_list(self):
        seen: dict = {}
        self.browser.launch(self.fake_playwright(seen), args=("--x",), timeout=5)
        self.assertEqual(seen["args"], ["--x"])
        self.assertEqual(seen["timeout"], 5)


if __name__ == "__main__":
    unittest.main()
