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
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config

from app import actions, settings

# group -> [(key, action, label)]
GROUPS: dict[str, list[tuple[str, str, str]]] = {
    '内容': [('1', 'analyze', '源码 → 手稿'),
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
    title_rest = (f" · {_config.app_name_zh()}  "
                  f"{_c('v' + info['tool_version'], PALETTE['hint'])}")
    product_plain = f' {_config.app_name()} · {_config.app_name_zh()}  v{info["tool_version"]}'
    book_plain = f' {info["title"]}  v{info["version"]}'
    book_line = (f' {_c(info["title"], PALETTE["book"])}'
                 f'  {_c("v" + info["version"], PALETTE["hint"])}')

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


def menu_text() -> str:
    """Grouped menu: group headers, aligned keys, one colour for actions."""
    lines: list[str] = []
    for group, entries in GROUPS.items():
        lines.append(f" {_c('▍', PALETTE['group'])}{_c(group, PALETTE['group'])}")
        for key, _action, label in entries:
            lines.append(f"   {_c(key, PALETTE['key'])}   {label}")
        lines.append('')
    lines.append(f"   {_c('c', PALETTE['key'])} 配置   "
                 f"{_c('r', PALETTE['key'])} 刷新   "
                 f"{_c('?', PALETTE['key'])} 帮助   "
                 f"{_c('q', PALETTE['key'])} 退出")
    return '\n'.join(lines)


def help_text() -> str:
    return ('数字键执行动作；`c` 进入配置修改（书名、版本、产物目录、语言、'
            '日志级别、LLM provider）；`r` 重新读取配置；`q` 退出。\n'
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


def _run(action: str) -> str:
    if action == 'settings':
        return configure()
    code, text = actions.run(action)
    return f'{text}\n[{_c("退出码 " + str(code), "32" if code == 0 else "31")}]'


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

    keys = {key: action for entries in GROUPS.values() for key, action, _ in entries}
    while True:
        sys.stdout.write('\n' + header() + '\n\n' + menu_text() + '\n\n> ')
        sys.stdout.flush()
        try:
            choice = (sys.stdin.readline() or '').strip().lower()
        except KeyboardInterrupt:   # Ctrl+C leaves the menu cleanly
            sys.stdout.write('\n')
            return 0
        if choice in ('q', 'quit', 'exit', '0', ''):
            return 0
        if choice in ('?', 'h', 'help'):
            print(help_text())
            continue
        if choice == 'r':
            settings._reload()
            print('配置已重新读取')
            continue
        if choice == 'c':
            print(configure())
            continue
        if choice in keys:
            print(_run(keys[choice]))
            continue
        print('无效选项，输入 ? 查看帮助')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
