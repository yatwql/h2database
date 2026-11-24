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


def retention_days() -> int:
    """How long any log survives; one policy for the rotating file and the reports."""
    return _settings()['retention_days']


def log_dir() -> str:
    """Absolute path of the log directory (created on demand)."""
    settings = _settings()
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
