#!/usr/bin/env python3
"""Shared actions for the CLI, TUI and Web entry points.

Every channel funnels into these functions so behaviour stays identical
regardless of how the toolchain is started.
"""
from __future__ import annotations

import contextlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import subprocess
import threading
import time

from lib import _config, _llm, _log

PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# How often a silent child reports that it is still working. Ten seconds is short
# enough to feel alive and long enough not to flood a two-minute render.
HEARTBEAT_S = 10.0


def repo_root() -> str:
    """Parent of the active book — the directory child scripts run in.

    A function, not a constant: an installed toolchain has no checkout, and the
    book is only known once the entry point has parsed --book.
    """
    return os.path.dirname(_config.current().root)
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
    'deliver-all': '手稿 → Markdown + HTML + EPUB + 标准版与印刷版 PDF',
    'print': '生成印刷版 PDF（章封面、点线目录、页眉页脚）',
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


def _unbuffered(command: list[str], env: dict) -> list[str]:
    """Put `-u` on the child and ask it for unbuffered output.

    A pipe makes the child block-buffer its own prints, so a three-minute render
    arrives in one lump at the end; both halves of the fix are needed.
    """
    env['PYTHONUNBUFFERED'] = '1'
    if len(command) > 1 and command[1] != '-u':
        return command[:1] + ['-u'] + command[1:]
    return command


def _stream(stream, on_line, clock=None) -> list[str]:
    """Forward the child's lines as they arrive; returns them all.

    A UI callback must never break the run it is reporting on, so a raising callback
    is suppressed instead of aborting the child.
    """
    chunks: list[str] = []
    for line in stream:
        chunks.append(line)
        if on_line is not None:
            with contextlib.suppress(Exception):
                on_line(line.rstrip())
    return chunks


def _heartbeat(on_line, started: float) -> tuple[threading.Event, threading.Thread]:
    """Start a thread that says 'still working' while the child is silent."""
    finished = threading.Event()

    def beat() -> None:
        while not finished.wait(HEARTBEAT_S):
            with contextlib.suppress(Exception):
                on_line(f'… 已用 {_clock(time.perf_counter() - started)}，仍在执行')

    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    return finished, thread


def _invoke(command: list[str], on_line=None) -> tuple[int, str]:
    """Run a child process, optionally reporting its output as it arrives.

    A build or a delivery can take minutes; a UI that only learns the outcome at the
    end can show nothing but a spinner. Streaming the child's own lines is the one
    honest progress signal — it is the same text that ends up in the report.
    """
    if on_line is None:
        proc = subprocess.run(command, capture_output=True, text=True,
                              cwd=repo_root(), check=False, env=child_env())
        return proc.returncode, (proc.stdout or '') + (proc.stderr or '')
    env = child_env()
    command = _unbuffered(command, env)
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True,
                               cwd=repo_root(), env=env)
    stream = process.stdout
    if stream is None:  # pragma: no cover - PIPE was requested just above
        return process.wait(), ''
    finished, _beater = _heartbeat(on_line, time.perf_counter())
    try:
        chunks = _stream(stream, on_line)
        return process.wait(), ''.join(chunks)
    finally:
        finished.set()


def _clock(seconds: float) -> str:
    """Elapsed time with its unit spelled out: `40 秒`, `1 分 40 秒`, `1 小时 5 分`."""
    total = int(seconds)
    if total < 60:
        return f'{total} 秒'
    if total < 3600:
        return f'{total // 60} 分 {total % 60:02d} 秒'
    return f'{total // 3600} 小时 {total % 3600 // 60} 分'


def _run(script: str, *args: str, on_line=None) -> tuple[int, str]:
    command = [sys.executable, os.path.join(PY_ROOT, script), *args]
    return _invoke(command, on_line)


def _make(*args: str, on_line=None) -> tuple[int, str]:
    return _invoke([sys.executable, MAKE, *args], on_line)


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


def build(on_line=None) -> tuple[int, str]:
    return _make('build', on_line=on_line)


def check(on_line=None) -> tuple[int, str]:
    return _make('check', on_line=on_line)


def test(on_line=None) -> tuple[int, str]:
    return _make('test', on_line=on_line)


def deliver(on_line=None) -> tuple[int, str]:
    return _make('deliver', on_line=on_line)


def print_edition(on_line=None) -> tuple[int, str]:
    """The print-grade PDF: render it, then judge it by the same rules as delivery.

    This is `make.py print` — one definition of the pipeline, so the TUI cannot
    produce a paper artifact that the step table would reject.
    """
    return _make('print', on_line=on_line)


def deliver_all(on_line=None) -> tuple[int, str]:
    """Every artifact in one run: Markdown + HTML, EPUB + PDF, then the print edition.

    Three steps in the order the dependencies force (a PDF renders from the HTML,
    the print edition renders from the same HTML), stopping at the first failure so
    a broken build cannot leave a half-updated `dist/` looking complete.
    """
    output = []
    for step in (build, deliver, print_edition):
        code, text = step(on_line=on_line)
        output.append(text)
        if code != 0:
            return code, ''.join(output)
    return 0, ''.join(output)


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
    'deliver-all': deliver_all,
    'print': print_edition,
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
        with _config.use(_config.Config(book, _SELECTION['edition'] or None)):
            return _dispatch(action, **kwargs)
    return _dispatch(action, **kwargs)


def _dispatch_build(action: str, on_line) -> tuple[int, str]:
    """The four report-producing actions, run so a caller can follow along."""
    if action == 'build':
        return build(on_line)
    if action == 'check':
        return check(on_line)
    if action == 'test':
        return test(on_line)
    if action == 'print':
        return print_edition(on_line)
    return deliver(on_line)


def _dispatch(action: str, **kwargs) -> tuple[int, str]:
    if action == 'llm-ask':
        return llm_ask(kwargs.get('prompt', ''), kwargs.get('scenario', 'summary'))
    if action in ('build', 'check', 'test', 'deliver', 'print'):
        return _dispatch_build(action, kwargs.get('on_progress'))
    if action == 'deliver-all':
        # the longest action: without a callback the caller sees silence for minutes
        return deliver_all(on_line=kwargs.get('on_progress'))
    if action in ANALYZE_ACTIONS:
        LOG.info('action %s start', action)
        code, text = analyze(use_llm=action == 'analyze-llm' or bool(kwargs.get('use_llm')),
                             refresh=action == 'analyze-refresh' or bool(kwargs.get('refresh')),
                             force=bool(kwargs.get('force')))
        LOG.info('action %s done rc=%s (%d chars, pid=%d)', action, code, len(text),
                 os.getpid())
        return code, text
    handler = DISPATCH.get(action)
    if handler is None:
        LOG.warning('unknown action %r', action)
        return 2, f'error: unknown action {action!r}; known: {", ".join(sorted(DISPATCH))}\n'
    LOG.info('action %s start (pid=%d, parent=%d)', action, os.getpid(), os.getppid())
    code, text = handler()
    LOG.info('action %s done rc=%s (%d chars, pid=%d)', action, code, len(text),
             os.getpid())
    return code, text
