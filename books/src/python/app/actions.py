#!/usr/bin/env python3
"""Shared actions for the CLI, TUI and Web entry points.

Every channel funnels into these functions so behaviour stays identical
regardless of how the toolchain is started.
"""
from __future__ import annotations

import os
import subprocess
import sys

from lib import _config, _llm, _log

PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.normpath(os.path.join(_config.BOOK_ROOT, '..'))
MAKE = os.path.join(PY_ROOT, 'make.py')
LOG = _log.get_logger('app')

ACTIONS = {
    'status': '显示书籍、配置与 LLM 状态',
    'analyze': '源码 → 手稿（digest → outline → chapters）',
    'build': '手稿 → 合并 Markdown + HTML',
    'check': '运行全部质量门禁',
    'test': '运行测试套件',
    'deliver': '构建 PDF 与 EPUB（按需）',
    'llm-ask': '用配置的 provider 回答一个问题',
    'doctor': '依赖与环境自检',
    'settings': '查看可修改的配置项',
}


def _run(script: str, *args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, os.path.join(PY_ROOT, script), *args],
                          capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def _make(*args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, MAKE, *args], capture_output=True, text=True,
                          cwd=REPO_ROOT, check=False)
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def status() -> tuple[int, str]:
    """Book identity, configuration layers and LLM routing."""
    versions = _config.versions()
    lines = [
        f"book      : {_config.TITLE or '(untitled)'} v{_config.VERSION}",
        (f"versions  : tool {versions['tool']}  source {versions['source']}  "
        f"doc {versions['doc']}"),
        f"manuscript: {_config.MANUSCRIPT_DIR}",
        f"dist      : {_config.DIST_DIR}",
        f"chapters  : {len(_config.chapter_files())} file(s)",
    ]
    try:
        llm = _llm.status()
        lines.append(f"llm       : default={llm['default_provider']} "
                     f"providers={', '.join(llm['providers'])}")
        lines.append(f"scenarios : {', '.join(llm['scenarios'])}")
    except _llm.LLMError as exc:
        lines.append(f"llm       : {exc}")
    return 0, '\n'.join(lines) + '\n'


def analyze() -> tuple[int, str]:
    """Run stage 1: digest the source tree, plan the outline, render chapters."""
    out = []
    for script in ('ingest/digest.py', 'ingest/outline.py', 'ingest/chapters.py'):
        code, text = _run(script)
        out.append(text)
        if code != 0:
            return code, '\n'.join(out)
    return 0, '\n'.join(out)


def build() -> tuple[int, str]:
    return _make('build')


def check() -> tuple[int, str]:
    return _make('check')


def test() -> tuple[int, str]:
    return _make('test')


def deliver() -> tuple[int, str]:
    return _make('deliver')


def llm_ask(prompt: str, scenario: str = 'summary') -> tuple[int, str]:
    """Ask the configured provider (mock by default)."""
    try:
        return 0, _llm.complete(prompt, scenario=scenario) + '\n'
    except _llm.LLMError as exc:
        return 2, f'error: {exc}\n'


def doctor() -> tuple[int, str]:
    return _make('doctor')


def settings_table() -> tuple[int, str]:
    """List the writable settings with their current values."""
    from app import settings as settings_module
    lines = [f"{'key':<14}{'value':<28}说明"]
    for row in settings_module.list_settings():
        lines.append(f"{row['key']:<14}{row['value']:<28}{row['description']}")
    return 0, '\n'.join(lines) + '\n'


DISPATCH = {
    'status': status,
    'doctor': doctor,
    'settings': settings_table,
    'analyze': analyze,
    'build': build,
    'check': check,
    'test': test,
    'deliver': deliver,
}


def run(action: str, **kwargs) -> tuple[int, str]:
    """Execute one action by name (used by every channel)."""
    if action == 'llm-ask':
        return llm_ask(kwargs.get('prompt', ''), kwargs.get('scenario', 'summary'))
    handler = DISPATCH.get(action)
    if handler is None:
        LOG.warning('unknown action %r', action)
        return 2, f'error: unknown action {action!r}; known: {", ".join(sorted(DISPATCH))}\n'
    LOG.info('action %s start', action)
    code, text = handler()
    LOG.info('action %s done rc=%s (%d chars)', action, code, len(text))
    return code, text
