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
from lib import _config, _errors, _fsutil

_fsutil.pin_stdout_utf8()


def _parser() -> argparse.ArgumentParser:
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
    parser.add_argument('--books-dir', default='',
                        help='directory holding several books; with no --book, a single '
                             'book inside it is used, several are listed')
    return parser


def _flag_errors(args) -> str:
    """The message for a flag used with the wrong action ('' when fine)."""
    if (args.force or args.refresh_facts) and args.action not in actions.ANALYZE_ACTIONS:
        return 'error: --force / --refresh-facts 只能用于 analyze 类动作'
    if args.force and args.refresh_facts:
        return 'error: --force 与 --refresh-facts 不能同时使用'
    return ''


def _book_from_dir(books_dir: str) -> tuple[str, int]:
    """(book root, 0) for a --books-dir with one book, else ('', 2) with the list."""
    found = _config.books_in(books_dir)
    if len(found) == 1:
        return found[0], 0
    if not found:
        sys.stderr.write(f'error: {books_dir} 下没有带 book.toml 的书\n')
        return '', 2
    sys.stderr.write(f'{books_dir} 下有 {len(found)} 本书，用 --book 指定其一：\n')
    for root in found:
        try:
            title = _config.Config(root).title
        except _config.ConfigError:
            title = '（配置读不出）'
        sys.stderr.write(f'  {title}  [{os.path.basename(root)}]  {root}\n')
    return '', 2


def _settings(book: str, args) -> int:
    """`settings`, plus the `settings set <key> <value>` write path."""
    tail = list(args.prompt)
    if tail and tail[0] == 'set':
        if len(tail) < 3:
            sys.stderr.write('usage: cli.py settings set <key> <value>\n')
            return 2
        try:
            with _config.use(_config.Config(book, args.edition or None)):
                stored = settings.set_value(tail[1], ' '.join(tail[2:]))
        except (KeyError, ValueError) as exc:
            sys.stderr.write(f'error: {exc}\n')
            return 2
        sys.stdout.write(f'{tail[1]} = {stored}\n')
        return 0
    code, text = actions.run('settings', book=book, edition=args.edition)
    sys.stdout.write(text)
    return code


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    invalid = _flag_errors(args)
    if invalid:
        sys.stderr.write(invalid + '\n')
        return 2
    if args.books_dir:
        os.environ['BOOKS_DIR'] = os.path.abspath(args.books_dir)

    book = _config.resolve_book_root(args.book or None)
    if args.books_dir and not args.book:
        book, code = _book_from_dir(args.books_dir)
        if code:
            return code
    if not os.path.isfile(os.path.join(book, 'data', 'book', 'book.toml')):
        sys.stderr.write(f'error: 没找到 book.toml，试过 {book}\n')
        return 2
    selection = {'book': book, 'edition': args.edition}

    if args.action == 'settings':
        return _settings(book, args)

    kwargs = {}
    if args.action == 'llm-ask':
        kwargs = {'prompt': ' '.join(args.prompt), 'scenario': args.scenario}
    elif args.action in actions.ANALYZE_ACTIONS:
        kwargs = {'force': args.force, 'refresh': args.refresh_facts}
    code, text = actions.run(args.action, **kwargs, **selection)
    sys.stdout.write(text)
    return code


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
