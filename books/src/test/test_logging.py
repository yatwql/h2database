#!/usr/bin/env python3
"""Tests for the logging layer: level control, file output, rotation config."""

import importlib
import io
import logging
import logging.handlers
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

import _fixture

TAGS = ("layer:infra", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, "lib"))

_config = importlib.import_module("lib._config")


class TestLogging(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.previous_level = os.environ.pop("BOOK_LOG_LEVEL", None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self.previous_level is not None:
            os.environ["BOOK_LOG_LEVEL"] = self.previous_level
        else:
            os.environ.pop("BOOK_LOG_LEVEL", None)

    def module(self):
        # handlers live on the named logger, so a reloaded module would keep writing
        # to the previous test's file: drop them before each load
        logger = logging.getLogger(_config.app_name())
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        return _fixture.load_module(self.root, "_log")

    def log_file(self) -> str:
        for handler in logging.getLogger(_config.app_name()).handlers:
            name = getattr(handler, "baseFilename", "")
            if name:
                return name
        name = _config.app_name()
        return os.path.join(self.root, "logs", f"{name}.log")

    def log_text(self) -> str:
        """Flush every handler and return the log file contents."""
        for handler in logging.getLogger(_config.app_name()).handlers:
            handler.flush()
        if not os.path.isfile(self.log_file()):
            return ""
        with open(self.log_file(), encoding="utf-8") as fh:
            return fh.read()

    def test_log_directory_created(self):
        log = self.module()
        self.assertTrue(os.path.isdir(log.log_dir()))

    def test_info_is_written(self):
        log = self.module()
        log.get_logger("t").info("info-message")
        self.assertIn("info-message", self.log_text())

    def test_default_level_is_info(self):
        log = self.module()
        self.assertEqual(log.describe()["level"], "INFO")

    def test_debug_hidden_at_info(self):
        log = self.module()
        log.setup("INFO")
        log.get_logger("t").debug("debug-hidden")
        self.assertNotIn("debug-hidden", self.log_text())

    def test_debug_shown_when_enabled(self):
        log = self.module()
        log.setup("DEBUG")
        log.get_logger("t").debug("debug-visible")
        self.assertIn("debug-visible", self.log_text())
        log.setup("INFO")

    def test_env_var_overrides_level(self):
        os.environ["BOOK_LOG_LEVEL"] = "debug"
        log = self.module()
        self.assertEqual(log.describe()["level"], "DEBUG")

    def test_daily_rotation_configured(self):
        log = self.module()
        log.setup("INFO")
        rotating = [
            h
            for h in logging.getLogger(_config.app_name()).handlers
            if isinstance(h, logging.handlers.TimedRotatingFileHandler)
        ]
        self.assertTrue(rotating, "a TimedRotatingFileHandler must be installed")
        handler = rotating[0]
        self.assertEqual(getattr(handler, "when", ""), "MIDNIGHT")
        self.assertGreater(getattr(handler, "backupCount", 0) or 0, 0)

    def test_make_run_writes_log(self):
        code, out = _fixture.run_inproc(self.root, "make.py", "check", "--only", "file_length")
        self.assertIn(code, (0, 1), out[-300:])
        import time

        deadline = time.time() + 2
        text = ""
        while time.time() < deadline:
            text = self.log_text()
            if f"{_config.app_name()}.make" in text:
                break
            time.sleep(0.05)
        self.assertIn(f"{_config.app_name()}.make", text)


class TestIsolationTest(unittest.TestCase):
    """A test run must never write into the book's own log."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.log_module = _fixture.load_module(self.root, "_log")

    def test_a_test_process_never_writes_the_repository_log(self):
        with mock.patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test_x"}):
            path = self.log_module.log_dir()
        repo_logs = os.path.join(os.path.dirname(self.root), "logs")
        self.assertFalse(os.path.abspath(path).startswith(os.path.abspath(repo_logs)))
        # a fixture book is a throwaway directory, so its own log is fine
        self.assertTrue(path.startswith(os.path.abspath(self.root)), path)

    def test_an_explicit_log_dir_wins(self):
        target = os.path.join(self.tmp.name, "logs")
        with mock.patch.dict(os.environ, {"BOOK_LOG_DIR": target}):
            self.assertEqual(os.path.abspath(self.log_module.log_dir()), os.path.abspath(target))


class _RaisingPolicy:
    """Stands in for `BASE_POLICY` when no book can be resolved."""

    def __init__(self, error):
        self.error = error

    def get(self, _key, _default=None):
        raise self.error("no book selected")


class LogDirBranchTest(unittest.TestCase):
    """Every way the log directory can fail, and what the caller sees."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.log = _fixture.load_module(self.root, "_log")
        # a real Config: `_settings()` reads the policy through it, and a stub would
        # only test the stub
        self.config = self.log._config.Config(self.root)
        self.addCleanup(self._clear_env)

    def _clear_env(self):
        for name in ("BOOK_LOG_DIR", "BOOK_LOG_LEVEL", "PYTEST_VERSION"):
            os.environ.pop(name, None)

    def test_settings_survive_an_unresolved_book(self):
        # the exception class must be the one `_log` catches: the fixture reloads
        # `lib._config`, so a stale module object has a different ConfigError
        with mock.patch.object(
            self.log._config, "BASE_POLICY", _RaisingPolicy(self.log._config.ConfigError)
        ):
            settings = self.log._settings()
        self.assertEqual(settings["level"], "INFO")
        self.assertEqual(settings["retention_days"], 14)

    def test_the_test_log_directory_survives_an_unresolved_book(self):
        with mock.patch.object(
            self.log._config, "app_name", side_effect=self.log._config.ConfigError("nope")
        ):
            path = self.log._test_log_dir()
        self.assertIn("tests-tests-", path)

    def test_an_unwritable_override_leaves_console_only(self):
        target = os.path.join(self.tmp.name, "denied")
        with (
            mock.patch.dict(os.environ, {"BOOK_LOG_DIR": target}),
            mock.patch.object(self.log.os, "makedirs", side_effect=OSError("denied")),
        ):
            self.assertEqual(self.log.log_dir(), "")
            self.assertEqual(self.log.log_file(), "")

    def test_a_test_process_logs_inside_its_fixture_book(self):
        with (
            mock.patch.object(self.log, "_is_test_process", return_value=True),
            mock.patch.object(self.log._config, "current", return_value=self.config),
        ):
            self.assertEqual(self.log.log_dir(), os.path.join(self.root, "logs"))

    def test_a_test_process_without_a_fixture_book_uses_its_own_directory(self):
        class Elsewhere:
            root = "/opt/some-book"

        with (
            mock.patch.object(self.log, "_is_test_process", return_value=True),
            mock.patch.object(
                self.log,
                "_settings",
                return_value={"level": "INFO", "dir": "logs", "retention_days": 14},
            ),
            mock.patch.object(self.log._config, "current", return_value=Elsewhere()),
            mock.patch.object(
                self.log, "_test_log_dir", return_value=os.path.join(self.tmp.name, "own")
            ),
        ):
            self.assertEqual(self.log.log_dir(), os.path.join(self.tmp.name, "own"))

    def test_an_uncreatable_test_directory_warns_and_leaves_console_only(self):
        stderr = io.StringIO()
        with (
            mock.patch.object(self.log, "_is_test_process", return_value=True),
            mock.patch.object(self.log._config, "current", return_value=self.config),
            mock.patch.object(self.log.os, "makedirs", side_effect=OSError("denied")),
            redirect_stderr(stderr),
        ):
            self.assertEqual(self.log.log_dir(), "")
        self.assertIn("cannot create log directory", stderr.getvalue())

    def test_a_selected_book_keeps_its_logs_under_its_root(self):
        with (
            mock.patch.object(self.log, "_is_test_process", return_value=False),
            mock.patch.object(self.log._config, "current", return_value=self.config),
        ):
            self.assertEqual(self.log.log_dir(), os.path.join(self.root, "logs"))

    def test_an_uncreatable_book_directory_falls_back_to_its_parent(self):
        stderr = io.StringIO()
        with (
            mock.patch.object(self.log, "_is_test_process", return_value=False),
            mock.patch.object(self.log._config, "current", return_value=self.config),
            mock.patch.object(self.log.os, "makedirs", side_effect=OSError("denied")),
            redirect_stderr(stderr),
        ):
            self.assertEqual(self.log.log_dir(), self.root)
        self.assertIn("cannot create log directory", stderr.getvalue())

    def test_without_a_book_there_is_no_log_directory(self):
        with (
            mock.patch.object(self.log, "_is_test_process", return_value=False),
            mock.patch.object(
                self.log._config, "current", side_effect=self.log._config.ConfigError("no book")
            ),
        ):
            self.assertEqual(self.log.log_dir(), "")

    def test_a_second_setup_keeps_the_handlers_and_only_moves_the_level(self):
        root_logger = self.log.setup("INFO")
        handlers = list(root_logger.handlers)
        again = self.log.setup()
        self.assertIs(again, root_logger)
        self.assertEqual(list(again.handlers), handlers)
        self.log.setup("DEBUG")
        self.assertEqual(again.level, logging.DEBUG)
        self.log.setup("INFO")

    def test_an_unopenable_log_file_still_leaves_a_console_handler(self):
        stderr = io.StringIO()
        with (
            mock.patch.object(self.log, "_CONFIGURED", False),
            mock.patch.object(self.log, "log_dir", return_value=self.tmp.name),
            mock.patch.object(
                self.log.logging.handlers, "TimedRotatingFileHandler", side_effect=OSError("denied")
            ),
            redirect_stderr(stderr),
        ):
            logger = self.log.setup("INFO")
        self.assertIn("file logging disabled", stderr.getvalue())
        self.assertTrue(logger.handlers)

    def test_retention_comes_from_the_policy(self):
        with mock.patch.object(
            self.log,
            "_settings",
            return_value={"level": "INFO", "dir": "logs", "retention_days": 7},
        ):
            self.assertEqual(self.log.retention_days(), 7)

    def test_a_test_process_without_a_selected_book_uses_its_own_directory(self):
        own = os.path.join(self.tmp.name, "own")
        with (
            mock.patch.dict(os.environ, {"BOOK_LOG_DIR": ""}),
            mock.patch.object(self.log, "_is_test_process", return_value=True),
            mock.patch.object(
                self.log._config, "current", side_effect=self.log._config.ConfigError("no book")
            ),
            mock.patch.object(self.log, "_test_log_dir", return_value=own),
        ):
            self.assertEqual(self.log.log_dir(), own)

    def test_pytest_without_its_env_markers_still_counts_as_a_test_process(self):
        with mock.patch.dict(
            os.environ, {"PYTEST_CURRENT_TEST": "", "BOOK_TEST_MODE": "", "PYTEST_VERSION": ""}
        ):
            self.assertTrue(self.log._is_test_process())

    def test_setup_without_a_writable_directory_stays_console_only(self):
        blocker = os.path.join(self.tmp.name, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("not a directory\n")
        with (
            mock.patch.dict(os.environ, {"BOOK_LOG_DIR": os.path.join(blocker, "logs")}),
            mock.patch.object(self.log, "_CONFIGURED", False),
        ):
            logger = self.log.setup("INFO")
            self.assertFalse(
                [
                    handler
                    for handler in logger.handlers
                    if isinstance(handler, logging.handlers.TimedRotatingFileHandler)
                ]
            )


if __name__ == "__main__":
    unittest.main()
