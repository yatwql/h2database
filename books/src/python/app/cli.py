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

from app import actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=sorted(actions.ACTIONS),
                        help='; '.join(f'{k}: {v}' for k, v in sorted(actions.ACTIONS.items())))
    parser.add_argument('prompt', nargs='*', help='prompt for llm-ask')
    parser.add_argument('--scenario', default='summary', help='LLM scenario for llm-ask')
    args = parser.parse_args(argv)

    kwargs = {}
    if args.action == 'llm-ask':
        kwargs = {'prompt': ' '.join(args.prompt), 'scenario': args.scenario}
    code, text = actions.run(args.action, **kwargs)
    sys.stdout.write(text)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
