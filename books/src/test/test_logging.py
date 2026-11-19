#!/usr/bin/env python3
"""Tests for the logging layer: level control, file output, rotation config."""
import importlib
import logging
import logging.handlers
import os
import sys
import tempfile
import unittest

import _fixture

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, 'lib'))

_config = importlib.import_module('lib._config')


class TestLogging(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.previous_level = os.environ.pop('BOOK_LOG_LEVEL', None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self.previous_level is not None:
            os.environ['BOOK_LOG_LEVEL'] = self.previous_level
        else:
            os.environ.pop('BOOK_LOG_LEVEL', None)

    def module(self):
        return _fixture.load_module(self.root, '_log')

    def log_file(self) -> str:
        name = _config.app_name()
        return os.path.join(self.root, 'logs', f'{name}.log')

    def log_text(self) -> str:
        """Flush every handler and return the log file contents."""
        for handler in logging.getLogger(_config.app_name()).handlers:
            handler.flush()
        if not os.path.isfile(self.log_file()):
            return ''
        with open(self.log_file(), encoding='utf-8') as fh:
            return fh.read()

    def test_log_directory_created(self):
        log = self.module()
        self.assertTrue(os.path.isdir(log.log_dir()))

    def test_info_is_written(self):
        log = self.module()
        log.get_logger('t').info('info-message')
        self.assertIn('info-message', self.log_text())

    def test_default_level_is_info(self):
        log = self.module()
        self.assertEqual(log.describe()['level'], 'INFO')

    def test_debug_hidden_at_info(self):
        log = self.module()
        log.setup('INFO')
        log.get_logger('t').debug('debug-hidden')
        self.assertNotIn('debug-hidden', self.log_text())

    def test_debug_shown_when_enabled(self):
        log = self.module()
        log.setup('DEBUG')
        log.get_logger('t').debug('debug-visible')
        self.assertIn('debug-visible', self.log_text())
        log.setup('INFO')

    def test_env_var_overrides_level(self):
        os.environ['BOOK_LOG_LEVEL'] = 'debug'
        log = self.module()
        self.assertEqual(log.describe()['level'], 'DEBUG')

    def test_daily_rotation_configured(self):
        log = self.module()
        log.setup('INFO')
        rotating = [h for h in logging.getLogger(_config.app_name()).handlers
                    if isinstance(h, logging.handlers.TimedRotatingFileHandler)]
        self.assertTrue(rotating, 'a TimedRotatingFileHandler must be installed')
        handler = rotating[0]
        self.assertEqual(getattr(handler, 'when', ''), 'MIDNIGHT')
        self.assertGreater(getattr(handler, 'backupCount', 0) or 0, 0)

    def test_make_run_writes_log(self):
        code, out = _fixture.run_inproc(self.root, 'make.py', 'check', '--only',
                                        'file_length')
        self.assertIn(code, (0, 1), out[-300:])
        import time
        deadline = time.time() + 2
        text = ''
        while time.time() < deadline:
            text = self.log_text()
            if f'{_config.app_name()}.make' in text:
                break
            time.sleep(0.05)
        self.assertIn(f'{_config.app_name()}.make', text)


if __name__ == '__main__':
    unittest.main()
