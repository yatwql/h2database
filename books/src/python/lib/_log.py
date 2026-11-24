#!/usr/bin/env python3
"""Logging setup for the books toolchain.

One log file per run day under ``books/logs/`` (rotated at midnight, kept for
``retention_days``). Level comes from, in order:

  1. ``BOOK_LOG_LEVEL`` environment variable (DEBUG/INFO/WARNING/ERROR),
  2. ``data/config/base.json`` -> ``logging.level``,
  3. INFO.

DEBUG adds per-step detail (arguments, durations, counts); INFO records the
run's key milestones; WARNING/ERROR stay quiet on stdout.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import tempfile

from lib import _config

_CONFIGURED = False
DEFAULT_FORMAT = '%(asctime)s %(levelname)-7s %(name)-18s %(message)s'


def _settings() -> dict:
    try:
        policy = _config.BASE_POLICY.get('logging') or {}
    except _config.ConfigError:
        # no book resolved yet: an installed toolchain is imported before --book is
        # parsed, and logging must not be the thing that aborts the run
        policy = {}
    return {
        'level': (os.environ.get('BOOK_LOG_LEVEL') or policy.get('level') or 'INFO').upper(),
        'dir': policy.get('dir') or 'logs',
        'retention_days': int(policy.get('retention_days') or 14),
    }


def _is_test_process() -> bool:
    """True inside a test run: pytest sets this for every test it executes."""
    return bool(os.environ.get('PYTEST_CURRENT_TEST') or os.environ.get('BOOK_TEST_MODE'))


def _test_log_dir() -> str:
    """Where a test run keeps its logs, so the book's own log stays untouched.

    A test that exercises an error path writes words like `unknown action 'nope'` into
    whatever log the process has — and for months those lines sat in the production
    log next to the real failures. Tests get their own directory; production keeps the
    file an operator reads.
    """
    try:
        name = _config.app_name()
    except _config.ConfigError:
        name = 'tests'
    return os.path.join(tempfile.gettempdir(), f'{name}-tests-{os.getpid()}', 'logs')


def log_file() -> str:
    """The rotating log file this process writes (empty when logging is off)."""
    folder = log_dir()
    return os.path.join(folder, f'{_config.app_name()}.log') if folder else ''


def tail_since(path: str, offset: int) -> tuple[list[str], int]:
    """Lines written since `offset`, with the new offset.

    A long action only tells its story through the log, so a UI that wants to say
    more than "still running" reads it here instead of inventing its own progress
    channel that would then disagree with the log.
    """
    if not path or not os.path.exists(path):
        return [], offset
    try:
        size = os.path.getsize(path)
        if size <= offset:
            return [], offset
        with open(path, encoding='utf-8', errors='replace') as handle:
            handle.seek(offset)
            text = handle.read()
    except OSError:
        return [], offset
    return [line for line in text.splitlines() if line.strip()], size


def retention_days() -> int:
    """How long any log survives; one policy for the rotating file and the reports."""
    return _settings()['retention_days']


def log_dir() -> str:
    """Absolute path of the log directory (created on demand)."""
    settings = _settings()
    override = os.environ.get('BOOK_LOG_DIR')
    if override:
        path = override
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            return ''  # console only
        return path
    if _is_test_process():
        # a test pointed at a fixture book logs inside that book: it is already a
        # throwaway directory, and the case can still assert what was written. A test
        # that never selected a book must not touch the repository's log at all.
        path = ''
        try:
            root = _config.current().root
        except _config.ConfigError:
            root = ''
        if root and os.path.abspath(root).startswith(tempfile.gettempdir()):
            path = os.path.join(root, settings['dir'])
        else:
            path = _test_log_dir()
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            sys.stderr.write(f'warning: cannot create log directory {path}: {exc}\n')
            return ''
        return path
    try:
        path = os.path.join(_config.current().root, settings['dir'])
    except _config.ConfigError:
        return ''  # console only until a book is selected
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f'warning: cannot create log directory {path}: {exc}\n')
        return os.path.dirname(path)
    return path


def setup(level: str | None = None) -> logging.Logger:
    """Configure the root logger once; returns the toolchain logger."""
    global _CONFIGURED
    settings = _settings()
    numeric = getattr(logging, (level or settings['level']).upper(), logging.INFO)
    root = logging.getLogger(_config.app_name())
    if _CONFIGURED:
        if level:  # only an explicit request changes the level after setup
            root.setLevel(numeric)
        return root

    # reconfigure cleanly: drop handlers left over from a previous setup
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    root.setLevel(numeric)
    root.propagate = False

    folder = log_dir()
    logfile = os.path.join(folder, f'{_config.app_name()}.log') if folder else ''
    if logfile:
        try:
            file_handler = logging.handlers.TimedRotatingFileHandler(
                logfile, when='midnight', backupCount=settings['retention_days'],
                encoding='utf-8')
        except OSError as exc:
            sys.stderr.write(f'warning: file logging disabled ({logfile}: {exc})\n')
        else:
            file_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
            root.addHandler(file_handler)

    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(logging.Formatter('%(levelname)s %(name)s: %(message)s'))
    console.setLevel(logging.WARNING)
    root.addHandler(console)

    _CONFIGURED = True
    root.debug('logging configured: file=%s level=%s retention=%s days',
               logfile, logging.getLevelName(numeric), settings['retention_days'])
    return root


def get_logger(name: str) -> logging.Logger:
    """Child logger; configuration happens on first call."""
    setup()
    return logging.getLogger(f'{_config.app_name()}.{name}')


def describe() -> dict:
    """Non-secret summary for CLIs and the web console."""
    settings = _settings()
    return {'level': settings['level'], 'dir': log_dir(),
            'retention_days': settings['retention_days']}
