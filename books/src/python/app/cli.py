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
from lib import _fsutil

_fsutil.pin_stdout_utf8()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=sorted(actions.ACTIONS),
                        help='; '.join(f'{k}: {v}' for k, v in sorted(actions.ACTIONS.items())))
    parser.add_argument('prompt', nargs='*', help='prompt for llm-ask')
    parser.add_argument('--scenario', default='summary', help='LLM scenario for llm-ask')
    args = parser.parse_args(argv)

    if args.action == 'settings':
        tail = list(args.prompt)
        if tail and tail[0] == 'set':
            if len(tail) < 3:
                sys.stderr.write('usage: cli.py settings set <key> <value>\n')
                return 2
            try:
                stored = settings.set_value(tail[1], ' '.join(tail[2:]))
            except (KeyError, ValueError) as exc:
                sys.stderr.write(f'error: {exc}\n')
                return 2
            sys.stdout.write(f'{tail[1]} = {stored}\n')
            return 0
        code, text = actions.run('settings')
        sys.stdout.write(text)
        return code

    kwargs = {}
    if args.action == 'llm-ask':
        kwargs = {'prompt': ' '.join(args.prompt), 'scenario': args.scenario}
    code, text = actions.run(args.action, **kwargs)
    sys.stdout.write(text)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
