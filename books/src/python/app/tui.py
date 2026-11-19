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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def _c(text: str, code: str) -> str:
    return f'\033[{code}m{text}\033[0m' if USE_COLOR else text


def header() -> str:
    """Book identity and the settings that matter most, as a boxed banner."""
    info = settings.summary()
    width = 68
    title = f" {info['title']}  v{info['version']} "
    line = '─' * max(0, width - len(title) - 2)
    rows = [
        _c(f"┌─{title}{line}─┐", '36;1'),
        f"│ 手稿  {info['manuscript']:<58}│",
        f"│ 产物  {info['dist']:<58}│",
        (f"│ 语言  {info['languages']:<14}日志 {info['log_level']:<8}"
        f"LLM {info['llm_provider']:<16}│"),
        _c(f"└{'─' * width}┘", '36;1'),
    ]
    return '\n'.join(rows)


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
