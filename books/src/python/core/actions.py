#!/usr/bin/env python3
"""Shared actions for the CLI, TUI and Web entry points.

Every channel funnels into these functions so behaviour stays identical
regardless of how the toolchain is started.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
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
    'analyze-llm': '源码 → 手稿（导读/小结用 LLM 润色，事实仍确定性）',
    'analyze-refresh': '源码 → 手稿（只刷新已标记的事实块，正文不动）',
    'build': '手稿 → 合并 Markdown + HTML',
    'check': '运行全部质量门禁',
    'test': '运行测试套件',
    'deliver': '构建 PDF 与 EPUB（按需）',
    'llm-ask': '用配置的 provider 回答一个问题',
    'doctor': '依赖与环境自检',
    'settings': '查看可修改的配置项',
}


# The book (and edition) the current run works on. Every child process reads it
# from the environment, which is how one selection reaches thirty scripts without
# threading a parameter through each of them.
_SELECTION: dict[str, str] = {'book': '', 'edition': ''}


def select(book: str = '', edition: str = '') -> None:
    """Pin the book and edition for this run (empty clears the pin)."""
    _SELECTION['book'] = book
    _SELECTION['edition'] = edition


def child_env() -> dict[str, str]:
    """Environment for a child process: the inherited one plus the selection."""
    env = dict(os.environ)
    if _SELECTION['book']:
        env['BOOK_ROOT'] = _SELECTION['book']
    if _SELECTION['edition']:
        env['BOOK_EDITION'] = _SELECTION['edition']
    return env


def _run(script: str, *args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, os.path.join(PY_ROOT, script), *args],
                          capture_output=True, text=True, cwd=REPO_ROOT, check=False,
                          env=child_env())
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def _make(*args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, MAKE, *args], capture_output=True, text=True,
                          cwd=REPO_ROOT, check=False, env=child_env())
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def status() -> tuple[int, str]:
    """Book identity, configuration layers and LLM routing."""
    versions = _config.versions()
    lines = [
        f"app       : {_config.app_title()}",
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


VOLUME_SCRIPT = 'audit/content_volume.py'


def _volume_line(payload: str) -> tuple[int, str]:
    """One-line verdict on the volume baseline, for the same report."""
    try:
        report = json.loads(payload)
    except (TypeError, ValueError):
        return 0, '内容体积：无基线可比（首版定稿后执行 --update-baseline 建立）'
    count = int(report.get('count') or 0)
    if not count:
        return 0, '内容体积：与基线一致（0 项低于下限）'
    return 1, (f'内容体积：{count} 项低于基线——先复核是否有章被覆盖或删减；'
               f'确认是有意收缩后执行 {VOLUME_SCRIPT} --update-baseline')


def _llm_lines(before: dict | None = None) -> str:
    """What this run cost, and the ceiling warning when one is configured."""
    try:
        lines = []
        if before is not None:
            lines.append(_llm.summary_line(before))
        else:
            line = _llm.usage_line()
            if line:
                lines.append(line)
        warning = _llm.budget_line()
        if warning:
            lines.append(warning)
        return '\n'.join(line for line in lines if line)
    except (_llm.LLMError, OSError) as exc:
        return f'LLM：用量记账不可用（{exc}）'


def analyze(use_llm: bool = False, force: bool = False,
            refresh: bool = False) -> tuple[int, str]:
    """Run stage 1: digest the source tree, plan the outline, render chapters.

    With ``use_llm`` the chapter lead-in and summary paragraphs may be drafted by
    the configured provider; facts, coordinates, tables and exercises stay
    deterministic either way. ``force`` lets the renderer overwrite chapters that
    already carry written prose (backing each one up first); ``refresh`` swaps
    only the marked generated blocks and leaves every other word in place.

    The run ends with the volume comparison, so "did the manuscript survive this
    ingest" is answered in the same report instead of a later gate.
    """
    out = []
    llm_before = _llm.take_totals() if use_llm else None
    for script in ('ingest/digest.py', 'ingest/outline.py', 'ingest/chapters.py'):
        extra = []
        if script.endswith('chapters.py'):
            extra = (['--llm'] if use_llm else [])
            extra += ['--refresh-facts'] if refresh else (['--force'] if force else [])
        code, text = _run(script, *extra)
        out.append(text)
        if code != 0:
            return code, '\n'.join(out)
    _code, report = _run(VOLUME_SCRIPT, '--json')
    volume_code, line = _volume_line(report)
    out.append(line)
    if use_llm:
        out.append(_llm_lines(llm_before))
        try:
            spent = _llm.since(llm_before or {})
        except (_llm.LLMError, OSError):
            spent = {'calls': 0}
        if not spent.get('calls'):
            out.append('说明：本轮没有生成或重写的章节，因此没有触发导读/小结润色；'
                       '要对已有正文润色加 --force（旧文件先备份），或按章用 --only。')
    return volume_code, '\n'.join(out)


def build() -> tuple[int, str]:
    return _make('build')


def check() -> tuple[int, str]:
    return _make('check')


def test() -> tuple[int, str]:
    return _make('test')


def deliver() -> tuple[int, str]:
    return _make('deliver')


def estimate_line(prompt: str, scenario: str = 'summary') -> str:
    """What one call is expected to cost, shown before the call is made."""
    guess = _llm.estimate(prompt, scenario)
    low, high = guess['cost_low'], guess['cost_high']
    currency = guess['currency']
    if low is None:
        money = '未定价'
    else:
        money = f'≈ {low:.4f}-{high:.4f} {currency}'
    spent = _llm.today_cost()
    today = f'；今日已用 ≈ {spent:.4f} {currency}' if spent else ''
    return (f"预计：{guess['model'] or '?'} 入 ~{guess['prompt_tokens']} token、"
            f"出 ≤{guess['max_tokens']} token，{money}{today}")


def llm_ask(prompt: str, scenario: str = 'summary') -> tuple[int, str]:
    """Ask the configured provider (mock by default), and report what it cost."""
    try:
        head = estimate_line(prompt, scenario)
    except _llm.LLMError as exc:
        head = f'预计：无法估价（{exc}）'
    try:
        text = _llm.complete(prompt, scenario=scenario)
    except _llm.LLMError as exc:
        return 2, f'{head}\nerror: {exc}\n'
    return 0, f'{head}\n{text}\n{_llm_lines()}\n'


def doctor() -> tuple[int, str]:
    return _make('doctor')


def settings_table() -> tuple[int, str]:
    """List the writable settings with their current values."""
    from core import settings as settings_module
    lines = [f"{'key':<14}{'value':<28}说明"]
    for row in settings_module.list_settings():
        lines.append(f"{row['key']:<14}{row['value']:<28}{row['description']}")
    return 0, '\n'.join(lines) + '\n'


DISPATCH = {
    'status': status,
    'doctor': doctor,
    'settings': settings_table,
    'analyze': analyze,
    'analyze-llm': lambda: analyze(use_llm=True),
    'analyze-refresh': lambda: analyze(refresh=True),
    'build': build,
    'check': check,
    'test': test,
    'deliver': deliver,
}

# Actions whose renderer step takes switches; forwarded to `analyze` as-is.
ANALYZE_ACTIONS = frozenset({'analyze', 'analyze-llm', 'analyze-refresh'})


def run(action: str, **kwargs) -> tuple[int, str]:
    """Execute one action by name (used by every channel).

    ``book`` and ``edition`` select what the action works on. Child processes read
    the selection from the environment; the few actions that run in-process read it
    from an active-config context, so both paths see the same book.
    """
    book = str(kwargs.get('book') or '')
    select(book, str(kwargs.get('edition') or ''))
    if book:
        with _config.use(_config.Config(book)):
            return _dispatch(action, **kwargs)
    return _dispatch(action, **kwargs)


def _dispatch(action: str, **kwargs) -> tuple[int, str]:
    if action == 'llm-ask':
        return llm_ask(kwargs.get('prompt', ''), kwargs.get('scenario', 'summary'))
    if action in ANALYZE_ACTIONS:
        LOG.info('action %s start', action)
        code, text = analyze(use_llm=action == 'analyze-llm' or bool(kwargs.get('use_llm')),
                             refresh=action == 'analyze-refresh' or bool(kwargs.get('refresh')),
                             force=bool(kwargs.get('force')))
        LOG.info('action %s done rc=%s (%d chars)', action, code, len(text))
        return code, text
    handler = DISPATCH.get(action)
    if handler is None:
        LOG.warning('unknown action %r', action)
        return 2, f'error: unknown action {action!r}; known: {", ".join(sorted(DISPATCH))}\n'
    LOG.info('action %s start', action)
    code, text = handler()
    LOG.info('action %s done rc=%s (%d chars)', action, code, len(text))
    return code, text
