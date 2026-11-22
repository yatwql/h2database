#!/usr/bin/env python3
"""Command-line entry point for the books toolchain.

  python app/cli.py status
  python app/cli.py analyze          # source -> manuscript
  python app/cli.py build            # manuscript -> markdown + html
  python app/cli.py check            # every quality gate
  python app/cli.py llm-ask "问题" --scenario summary
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import actions, settings
from lib import _config, _fsutil

_fsutil.pin_stdout_utf8()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=sorted(actions.ACTIONS),
                        help='; '.join(f'{k}: {v}' for k, v in sorted(actions.ACTIONS.items())))
    parser.add_argument('prompt', nargs='*', help='prompt for llm-ask')
    parser.add_argument('--scenario', default='summary', help='LLM scenario for llm-ask')
    parser.add_argument('--force', action='store_true',
                        help='analyze: overwrite chapters that already carry prose '
                             '(each previous file is backed up)')
    parser.add_argument('--refresh-facts', action='store_true',
                        help='analyze: replace only the marked fact blocks')
    parser.add_argument('--book', default='',
                        help='book root to work on (default: BOOK_ROOT, then the '
                             'nearest ancestor holding data/book/book.toml)')
    parser.add_argument('--edition', default='', help='manuscript edition to work on')
    args = parser.parse_args(argv)

    if (args.force or args.refresh_facts) and args.action not in actions.ANALYZE_ACTIONS:
        sys.stderr.write('error: --force / --refresh-facts 只能用于 analyze 类动作\n')
        return 2
    if args.force and args.refresh_facts:
        sys.stderr.write('error: --force 与 --refresh-facts 不能同时使用\n')
        return 2
    book = _config.resolve_book_root(args.book or None)
    marker = os.path.join(book, 'data', 'book', 'book.toml')
    if not os.path.isfile(marker):
        sys.stderr.write(f'error: 没找到 book.toml，试过 {book}\n')
        return 2
    selection = {'book': book, 'edition': args.edition}

    if args.action == 'settings':
        tail = list(args.prompt)
        if tail and tail[0] == 'set':
            if len(tail) < 3:
                sys.stderr.write('usage: cli.py settings set <key> <value>\n')
                return 2
            try:
                with _config.use(_config.Config(book)):
                    stored = settings.set_value(tail[1], ' '.join(tail[2:]))
            except (KeyError, ValueError) as exc:
                sys.stderr.write(f'error: {exc}\n')
                return 2
            sys.stdout.write(f'{tail[1]} = {stored}\n')
            return 0
        code, text = actions.run('settings', **selection)
        sys.stdout.write(text)
        return code

    kwargs = {}
    if args.action == 'llm-ask':
        kwargs = {'prompt': ' '.join(args.prompt), 'scenario': args.scenario}
    elif args.action in actions.ANALYZE_ACTIONS:
        kwargs = {'force': args.force, 'refresh': args.refresh_facts}
    code, text = actions.run(args.action, **kwargs, **selection)
    sys.stdout.write(text)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
