#!/usr/bin/env python3
"""Traceability between the gate table in testplan.md and make.py.

Every gate that `make.py` runs must be described in the testplan, and every
script named there must exist and be wired into `make.py`. This keeps the
quality manual and the toolchain from drifting apart.

Usage:
  python gate_trace.py
  python gate_trace.py --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

TESTPLAN = os.path.join(_config.DOCS_DIR, 'managements', 'testplan.md')
PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKE_PY = os.path.join(PY_ROOT, 'make.py')
SCRIPT_RE = re.compile(r'`((?:(?:audit|ingest|manuscript|render|lib)/)?[a-z_]+\.py)`')
STEP_RE = re.compile(r"\('([a-z_]+)', '((?:audit|ingest|manuscript|render)/[a-z_]+\.py)'")


def gate_scripts() -> dict[str, str]:
    """make.py: gate name -> script path."""
    text = _fsutil.read_text(MAKE_PY)
    return dict(STEP_RE.findall(text))


def testplan_scripts() -> set[str]:
    text = _fsutil.read_text(TESTPLAN)
    return set(SCRIPT_RE.findall(text))


def available() -> set[str]:
    root = os.path.join(_config.BOOK_ROOT, 'src', 'python')
    return {os.path.relpath(p, root).replace(os.sep, '/')
            for p in glob.glob(os.path.join(root, '**', '*.py'), recursive=True)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    gates = gate_scripts()
    documented_paths = testplan_scripts()
    documented = {os.path.basename(p) for p in documented_paths}
    present_paths = available()
    present = {os.path.basename(p) for p in present_paths}
    gate_basenames = {os.path.basename(p) for p in gates.values()}
    problems: list[str] = []

    for name, script in sorted(gates.items()):
        if os.path.basename(script) not in documented:
            problems.append(f'make.py gate "{name}" ({script}) is not described in testplan.md')
        if script not in present_paths:
            problems.append(f'make.py gate "{name}" points at a missing script: {script}')
    for script in sorted(documented_paths):
        base = os.path.basename(script)
        if base == 'make.py':
            continue  # the runner names itself; it is not a gate
        if base not in present:
            problems.append(f'testplan.md names a missing script: {script}')
        elif base not in gate_basenames:
            problems.append(f'testplan.md names {script} but make.py does not run it')

    if args.json:
        print(json.dumps({'gates': len(gates), 'documented': len(documented),
                          'count': len(problems), 'problems': problems},
                         ensure_ascii=False, indent=2))
        return 0 if not problems else 1

    if not problems:
        print(f'✅ 门禁可追溯（{len(gates)} 个 make.py 门禁全部在 testplan 中登记）')
        return 0
    print(f'门禁可追溯性问题 {len(problems)} 处：')
    for problem in problems:
        print(f'  - {problem}')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
