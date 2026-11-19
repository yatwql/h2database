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


def _width(text: str) -> int:
    """Display width: CJK and fullwidth characters take two columns."""
    return sum(2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
               for ch in text)


def _c(text: str, code: str) -> str:
    return f'\033[{code}m{text}\033[0m' if USE_COLOR else text


def header() -> str:
    """Two identity lines (product, then book) above the operational facts."""
    info = settings.summary()
    product = f" {_config.app_name()} · {_config.app_name_zh()}  v{info['tool_version']}"
    book = f" {info['title']}  v{info['version']}"
    source = info['source_dir'] or '(未配置)'
    facts = [
        f" 源码 {source}  ({info['source_version']})",
        f" 手稿 {info['manuscript']}",
        f" 产物 {info['dist']}",
        f" 语言 {info['languages']}  日志 {info['log_level']}  LLM {info['llm_provider']}",
    ]
    inner = max(_width(text) for text in [product, book, *facts]) + 1

    def line(text: str) -> str:
        return f"│{text}{' ' * (inner - _width(text))}│"

    border = '─' * inner
    return '\n'.join([
        _c(f'┌{border}┐', '36'),
        _c(line(product), '96;1'),        # bright cyan: the software itself
        _c(line(book), '93;1'),           # bright yellow: the book being built
        _c(f'├{border}┤', '36'),
        *[line(text) for text in facts],
        _c(f'└{border}┘', '36'),
    ])


def menu_text() -> str:
    """Grouped menu; every entry is `<key>) <label>`."""
    lines: list[str] = []
    for group, entries in GROUPS.items():
        lines.append(_c(f' {group}', '33;1'))
        for key, _action, label in entries:
            lines.append(f"   {_c(key + ')', '32')} {label}")
    lines.append('')
    lines.append(f"   {_c('c)', '32')} 修改配置      {_c('r)', '32')} 刷新"
                 f"      {_c('?', '32')} 帮助      {_c('q)', '32')} 退出")
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
        choice = (sys.stdin.readline() or '').strip().lower()
        if choice in ('q', 'quit', 'exit', ''):
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
