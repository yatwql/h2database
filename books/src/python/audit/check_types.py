#!/usr/bin/env python3
"""Run the static type checker over the toolchain (optional gate).

Uses pyright when it is on PATH (CI installs it); otherwise reports a skip and
exits 0 so local runs stay usable. Configuration: pyrightconfig.json.

Usage:
  python check_types.py
  python check_types.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config

REPO_ROOT = os.path.normpath(os.path.join(_config.BOOK_ROOT, '..'))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    binary = shutil.which('pyright')
    if binary is None:
        if args.json:
            print(json.dumps({'status': 'skip', 'reason': 'pyright not installed'}, indent=2))
        else:
            print('pyright 未安装，跳过类型检查（CI 会执行）')
        return 0

    proc = subprocess.run([binary, '--outputjson'], capture_output=True, text=True,
                          cwd=REPO_ROOT, check=False)
    try:
        payload = json.loads(proc.stdout or '{}')
    except json.JSONDecodeError:
        payload = {}
    errors = payload.get('summary', {}).get('errorCount', 0)

    if args.json:
        print(json.dumps({'status': 'ok' if proc.returncode == 0 else 'fail',
                          'errors': errors}, indent=2))
        return 0 if proc.returncode == 0 else 1

    if proc.returncode == 0:
        print('✅ 类型检查通过')
        return 0
    print(f'类型检查失败：{errors} 个错误')
    for diagnostic in (payload.get('generalDiagnostics') or [])[:20]:
        location = diagnostic.get('file', '')
        line = diagnostic.get('range', {}).get('start', {}).get('line', 0) + 1
        print(f"  {location}:{line}  {diagnostic.get('message', '')[:100]}")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
