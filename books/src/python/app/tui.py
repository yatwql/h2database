#!/usr/bin/env python3
"""Terminal UI: grouped actions, live configuration and a compact dashboard.

  python app/tui.py                # interactive
  python app/tui.py --once status  # one action, then exit (scriptable)

Keys: number = run action, c = configure, r = refresh, ? = help, q = quit.
Colour is used only on a real terminal and can be disabled with NO_COLOR=1.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config

from app import actions, keys, settings

# group -> [(key, action, label)]
GROUPS: dict[str, list[tuple[str, str, str]]] = {
    '内容': [('1', 'analyze', '源码 → 手稿'),
             ('l', 'analyze-llm', '源码 → 手稿（LLM 润色导读/小结）'),
             ('2', 'build', '手稿 → Markdown + HTML'),
             ('3', 'deliver', 'PDF + EPUB（按需）')],
    '质量': [('4', 'check', '全部质量门禁'),
             ('5', 'test', '测试套件（快档）')],
    '配置与状态': [('6', 'status', '书籍 / 配置 / LLM 状态'),
                   ('7', 'llm-ask', '用配置的 provider 提问'),
                   ('8', 'settings', '查看与修改配置'),
                   ('9', 'doctor', '依赖与环境')],
}

USE_COLOR = sys.stdout.isatty() and not os.environ.get('NO_COLOR')

# One palette, used everywhere: chrome is quiet, identity is bright, keys are
# the only saturated colour in the menu so the eye lands on what is actionable.
PALETTE = {
    'frame': '38;5;240',        # dim grey: borders and rules
    'label': '38;5;245',        # muted grey: field labels
    'value': '38;5;252',        # near-white: field values
    'product': '1;38;5;231',    # bold bright white: the software itself
    'product_accent': '1;38;5;45',   # bright cyan: product name
    'book': '1;38;5;222',       # bright warm yellow: the book being built
    'book_accent': '38;5;179',
    'group': '1;38;5;45',       # bright cyan: menu groups
    'key': '1;38;5;114',        # bright green: what you can press
    'ok': '38;5;114',
    'warn': '38;5;221',
    'error': '38;5;203',
    'hint': '38;5;244',
    'cursor': '1;38;5;231',      # the highlighted row
    'cursor_bar': '1;38;5;45',   # its leading marker
    'value_ok': '38;5;114',
    'llm_badge': '38;5;179',   # amber: this row spends LLM tokens
}


def _width(text: str) -> int:
    """Display width: CJK and fullwidth characters take two columns."""
    return sum(2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
               for ch in text)


def _c(text: str, code: str) -> str:
    return f'\033[{code}m{text}\033[0m' if USE_COLOR else text


def header() -> str:
    """Identity on top, operational facts below, chrome kept quiet."""
    info = settings.summary()
    source = info['source_dir'] or '(未配置)'
    # (label, value) pairs: labels are muted, values near-white.
    facts = [
        ('源码', f"{source}  {_c('(' + info['source_version'] + ')', PALETTE['hint'])}"),
        ('手稿', info['manuscript']),
        ('产物', info['dist']),
        ('语言', '{}   {} {}   {} {}'.format(
            info['languages'], _c('日志', PALETTE['label']), info['log_level'],
            _c('LLM', PALETTE['label']), info['llm_provider'])),
    ]
    label_width = max(_width(label) for label, _value in facts) + 1

    title_left = _c(_config.app_name(), PALETTE['product_accent'])
    updated = _config.tool_updated()
    title_rest = (f" · {_config.app_name_zh()}  "
                  f"{_c('v' + info['tool_version'], PALETTE['hint'])}"
                  + (f"  {_c('更新 ' + updated, PALETTE['hint'])}" if updated else ''))
    product_plain = (f' {_config.app_name()} · {_config.app_name_zh()}  '
                     f'v{info["tool_version"]}'
                     + (f'  更新 {updated}' if updated else ''))
    book_date = _config.book_updated()
    book_plain = (f' 书籍 {info["title"]}  v{info["version"]}'
                  + (f'  更新 {book_date}' if book_date else ''))
    book_line = (f' {_c("书籍", PALETTE["label"])} '
                 f'{_c(info["title"], PALETTE["book"])}'
                 f'  {_c("v" + info["version"], PALETTE["hint"])}'
                 + (f'  {_c("更新 " + book_date, PALETTE["hint"])}' if book_date else ''))

    inner = max(_width(product_plain), _width(book_plain),
                max(_width(f' {label} {value}') for label, value in facts)) + 1

    def pad(plain: str, rendered: str) -> str:
        return f"{rendered}{' ' * (inner - _width(plain))}"

    def fact_line(label: str, value: str) -> str:
        gap = ' ' * (label_width - _width(label))
        plain = f' {label}{gap}{value}'
        rendered = f' {_c(label, PALETTE["label"])}{gap}{value}'
        return _c('│', PALETTE['frame']) + pad(plain, rendered) + _c('│', PALETTE['frame'])

    product_line = pad(product_plain, ' ' + title_left + title_rest)
    book_padded = pad(book_plain, book_line)
    rows = [
        _c('╭' + '─' * inner + '╮', PALETTE['frame']),
        product_line,
        book_padded,
        _c('├' + '─' * inner + '┤', PALETTE['frame']),
        *[fact_line(label, value) for label, value in facts],
        _c('╰' + '─' * inner + '╯', PALETTE['frame']),
    ]
    # product/book lines need their frame characters painted without colour bleed
    rows[1] = rows[1].replace('╭', '│', 0)
    rows[1] = _c('│', PALETTE['frame']) + rows[1] + _c('│', PALETTE['frame'])
    rows[2] = _c('│', PALETTE['frame']) + rows[2] + _c('│', PALETTE['frame'])
    return '\n'.join(rows)


ENTRIES: list[tuple[str, str, str]] = [entry for entries in GROUPS.values()
                                       for entry in entries]

# Entries whose output depends on the LLM carry a badge, so the plain and the
# LLM path are never mistaken for each other at a glance.
LLM_ACTIONS = {'analyze-llm', 'llm-ask'}

# The cursor starts on the everyday action (hand-written manuscript -> built
# HTML), not on the ingest step, so opening the menu and pressing Enter does the
# common thing.
DEFAULT_ENTRY_KEY = '2'


def default_cursor() -> int:
    """Index of the entry the menu starts on (0 when the key is missing)."""
    for index, entry in enumerate(ENTRIES):
        if entry[0] == DEFAULT_ENTRY_KEY:
            return index
    return 0


def menu_text(cursor: int | None = None) -> str:
    """Grouped menu; `cursor` highlights one row (↑/↓ moves it)."""
    lines: list[str] = []
    index = 0
    for group, entries in GROUPS.items():
        lines.append(f" {_c('▍', PALETTE['group'])}{_c(group, PALETTE['group'])}")
        for key, _action, label in entries:
            marker = '❯' if cursor == index else ' '
            label_style = PALETTE['cursor'] if cursor == index else PALETTE['value']
            badge = (f" {_c('LLM', PALETTE['llm_badge'])}"
                     if _action in LLM_ACTIONS else '')
            lines.append(f" {_c(marker, PALETTE['cursor_bar'])} "
                         f"{_c(key, PALETTE['key'])}   {_c(label, label_style)}{badge}")
            index += 1
        lines.append('')
    lines.append(f"   {_c('c', PALETTE['key'])} 配置   "
                 f"{_c('r', PALETTE['key'])} 刷新   "
                 f"{_c('?', PALETTE['key'])} 帮助")
    lines.append(f"   {_c('q', PALETTE['key'])} / {_c('0', PALETTE['key'])} 退出"
                 f"   {_c('Ctrl+C', PALETTE['key'])} 退出")
    lines.append(f"   {_c('↑/↓', PALETTE['key'])} 选择 · "
                 f"{_c('Enter', PALETTE['key'])} 执行 · "
                 f"数字键直达")
    return '\n'.join(lines)


def help_text() -> str:
    return ('数字键执行动作；`c` 进入配置修改（书名、版本、产物目录、语言、'
            '日志级别、LLM provider）；`r` 重新读取配置。\n'
            '退出：`q`、`0` 或 `Ctrl+C`（三者都走同一条干净退出路径）。\n'
            '非交互场景用 `--once <动作>`，例如 `--once status`。')


def configure(reader=input) -> str:
    """Interactive editor for the writable settings (returns a log line)."""
    lines = ['可修改项：']
    rows = settings.list_settings()
    for index, row in enumerate(rows, start=1):
        lines.append(f"  {index}) {row['key']:<14} {row['value']:<24} {row['description']}")
    print('\n'.join(lines))
    choice = (reader('选择要修改的序号（回车取消）: ') or '').strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(rows):
        return '未修改'
    key = rows[int(choice) - 1]['key']
    value = (reader(f"{key} 的新值（当前 {rows[int(choice) - 1]['value']}）: ") or '').strip()
    if not value:
        return '未修改'
    try:
        stored = settings.set_value(key, value)
    except (KeyError, ValueError) as exc:
        return f'修改失败：{exc}'
    return f'已更新 {key} = {stored}'


# Actions that rewrite many artifacts and take minutes: ask once before running.
CONFIRM_ACTIONS = {'deliver'}
TAIL_LINES = 15


def _tail(text: str, limit: int = TAIL_LINES) -> str:
    """Last ``limit`` lines of an action's output (progress, not a wall of text)."""
    lines = [line for line in (text or '').splitlines() if line.strip()]
    if not lines:
        return ''
    shown = lines[-limit:]
    prefix = f'…（前 {len(lines) - len(shown)} 行略）' if len(lines) > len(shown) else ''
    return ('\n' + prefix + '\n' if prefix else '\n') + '\n'.join(shown)


def confirm(question: str, reader=input) -> bool:
    """y/N prompt for actions worth a second look."""
    answer = (reader(f'{question} [y/N] ') or '').strip().lower()
    return answer in ('y', 'yes', '是')


def run_entry(action: str, label: str) -> str:
    """Run one action and report what happened: status, tail, timing, exit code."""
    if action == 'settings':
        return configure()
    if action in CONFIRM_ACTIONS and not confirm(f'{label} 会重建全部产物，继续？'):
        return _c('已取消', PALETTE['hint'])
    started = time.perf_counter()
    sys.stdout.write(_c(f'⠿ 正在执行 {label}（{action}）…', PALETTE['hint']) + '\n')
    sys.stdout.flush()
    code, text = actions.run(action)
    elapsed = time.perf_counter() - started
    lines = [line for line in (text or '').splitlines() if line.strip()]
    verdict = _c('✓ 完成', PALETTE['value_ok']) if code == 0 else _c('✗ 失败', PALETTE['error'])
    summary = (f'{verdict}  {label}  用时 {elapsed:.1f}s  '
               f'退出码 {code}  输出 {len(lines)} 行')
    return (f'{_tail(text)}\n{summary}\n'
            f'{_c("详情见 books/logs/", PALETTE["hint"])}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--once', metavar='ACTION', help='run one action and exit')
    args = parser.parse_args(argv)

    if args.once:
        if args.once == 'settings':
            sys.stdout.write(configure())
            return 0
        code, text = actions.run(args.once)
        sys.stdout.write(text)
        return code

    shortcuts = {key: (action, label) for key, action, label in ENTRIES}
    cursor = default_cursor()
    status = ''
    while True:
        screen = ['\n' + header(), '', menu_text(cursor)]
        if status:
            screen += ['', status]
        screen += ['', _c('❯ ', PALETTE['cursor_bar'])]
        sys.stdout.write('\n'.join(screen))
        sys.stdout.flush()
        status = ''
        try:
            pressed = keys.normalize(keys.read_key())
        except KeyboardInterrupt:      # Ctrl+C leaves the menu cleanly
            sys.stdout.write('\n')
            return 0

        if pressed in ('q', '0', keys.KEY_ESC, keys.KEY_CTRL_C):
            return 0
        if pressed == keys.KEY_UP:
            cursor = (cursor - 1) % len(ENTRIES)
            continue
        if pressed == keys.KEY_DOWN:
            cursor = (cursor + 1) % len(ENTRIES)
            continue
        if pressed == keys.KEY_ENTER:
            action, label = ENTRIES[cursor][1], ENTRIES[cursor][2]
            status = run_entry(action, label)
            continue
        if pressed in ('?', 'h'):
            print(help_text())
            continue
        if pressed == 'r':
            settings._reload()
            status = _c('配置已重新读取', PALETTE['value_ok'])
            continue
        if pressed == 'c':
            status = configure()
            continue
        if pressed in shortcuts:
            index = next(i for i, entry in enumerate(ENTRIES) if entry[0] == pressed)
            cursor = index
            action, label = shortcuts[pressed]
            status = run_entry(action, label)
            continue
        status = _c(f'无效按键 {pressed!r}，按 ? 查看帮助', PALETTE['warn'])

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
