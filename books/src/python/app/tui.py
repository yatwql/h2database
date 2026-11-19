#!/usr/bin/env python3
"""Terminal UI: a numbered menu over the shared actions.

  python app/tui.py              # interactive menu
  python app/tui.py --once status  # run one action and exit (scriptable)
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import actions


def menu_text() -> str:
    rows = [f'  {index}. {name:<8} {desc}'
            for index, (name, desc) in enumerate(sorted(actions.ACTIONS.items()), start=1)]
    return '书籍工具链\n' + '\n'.join(rows) + '\n  q. 退出\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--once', metavar='ACTION', help='run one action and exit')
    args = parser.parse_args(argv)

    if args.once:
        code, text = actions.run(args.once)
        sys.stdout.write(text)
        return code

    names = sorted(actions.ACTIONS)
    while True:
        sys.stdout.write('\n' + menu_text() + '请选择: ')
        sys.stdout.flush()
        choice = (sys.stdin.readline() or '').strip().lower()
        if choice in ('q', 'quit', 'exit', ''):
            return 0
        if not choice.isdigit() or not 1 <= int(choice) <= len(names):
            sys.stdout.write('无效选项\n')
            continue
        code, text = actions.run(names[int(choice) - 1])
        sys.stdout.write(text)
        sys.stdout.write(f'\n[退出码 {code}]\n')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
