#!/usr/bin/env python3
"""The print edition: the delivery renderer plus `print_profile`'s typography.

Why this is thin: the print edition and the delivery PDF must agree on the page
box, the column, the code size and the pagination, so both go through
`render.pdf_split`. What a printed page may add — chapter banners, TOC dot leaders —
lives in `render.print_profile`, in `em` and behind `@media print`. Nothing here
sets a scale or a margin: those belong to `lib.layout`, and a second copy of them is
what let the print edition run its text 642pt wide on a 595pt sheet.

Steps (each callable, engine injectable, so tests need no browser):

  build(html_path, pdf_path, engine)   inject the profile, split-render, report
  main(argv, engine)                   CLI: regenerate the HTML, then build
"""
from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import contextlib
import os
import subprocess
from typing import Any

from lib import _config, _errors, _fsutil
from render import pdf_split, print_profile

_fsutil.pin_stdout_utf8()

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..', '..'))
generate_script = os.path.join(script_dir, 'to_html.py')


def build(html_path: str | None = None, pdf_path: str | None = None,
          engine: Any = None) -> int:
    """Render the print edition; returns the page count."""
    source = html_path or _config.merged_html()
    target = pdf_path or _config.merged_print_pdf()
    html = _fsutil.read_text(source)
    print(f'  读取 {os.path.basename(source)}（{os.path.getsize(source) / 1048576:.2f} MB）',
          flush=True)
    print(f'  {print_profile.describe()}')

    staging = _config.dist(f'_{_config.MERGED_NAME}-print.html')
    _fsutil.write_text(staging, print_profile.inject(html))
    try:
        print('  Chromium 分章渲染中（与标准版同一页框）…', flush=True)
        count = pdf_split.render_html(staging, target, engine=engine)
    finally:
        with contextlib.suppress(OSError):
            os.remove(staging)
    print(f'  Rendered: {target}（{count} 页）')
    return count


def main(argv: list[str] | None = None, engine: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--html', help='source HTML (default: merged HTML)')
    parser.add_argument('--pdf', help='target PDF (default: print-grade PDF)')
    parser.add_argument('--skip-html', action='store_true',
                        help='do not regenerate the HTML before printing')
    args = parser.parse_args(argv)

    if not args.skip_html and os.path.exists(generate_script):
        result = subprocess.run([_sys.executable, generate_script],
                                capture_output=True, text=True, encoding='utf-8',
                                cwd=repo_root, check=False)
        print(result.stdout)
        if result.returncode != 0:
            print('HTML generation FAILED:', result.stderr, file=_sys.stderr)
            return 1
    try:
        build(args.html, args.pdf, engine)
    except Exception as exc:
        print(f'  print-grade PDF FAILED: {exc}', file=_sys.stderr)
        return 1
    print(f'Print-grade PDF: {args.pdf or _config.merged_print_pdf()}')
    return 0


if __name__ == '__main__':
    _sys.exit(_errors.run(main, _sys.argv[1:]))
