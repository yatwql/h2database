#!/usr/bin/env python3
"""Enforce where the LLM may be used ("用在刀刃上").

Policy (data/config/llm_settings.json -> policy):
- prose scenarios may call the LLM (chapter-draft, chapter-polish, summary,
  review);
- everything factual stays deterministic: gates, coordinates, cross refs,
  links, duplicates, metrics, captions, index, glossary, tables.

The check is structural: only the app layer (and ingest chapter rendering)
may import ``lib._llm``; audit/ gates must never do so.

Usage:
  python llm_policy.py            # report + exit code
  python llm_policy.py --json
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

PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_LAYERS = ('app', 'ingest')
IMPORT_RE = re.compile(r'^\s*(?:from\s+lib\s+import\s+[^\n]*\b_llm\b|import\s+lib\._llm)', re.MULTILINE)


def policy() -> dict:
    try:
        return json.loads(_fsutil.read_text(
            os.path.join(_config.BOOK_ROOT, 'data', 'config', 'llm_settings.json'))
        ).get('policy') or {}
    except (OSError, json.JSONDecodeError):
        return {}


def offenders() -> list[dict]:
    """Files that import the LLM layer without being allowed to."""
    found: list[dict] = []
    for path in glob.glob(os.path.join(PY_ROOT, '**', '*.py'), recursive=True):
        if '__pycache__' in path:
            continue
        rel = os.path.relpath(path, PY_ROOT).replace(os.sep, '/')
        layer = rel.split('/')[0] if '/' in rel else ''
        if layer in ALLOWED_LAYERS or rel.startswith('lib/'):
            continue
        text = _fsutil.read_text(path)
        if IMPORT_RE.search(text):
            found.append({'file': rel, 'layer': layer})
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    pol = policy()
    found = offenders()

    if args.json:
        print(json.dumps({'policy': pol, 'offenders': found}, ensure_ascii=False, indent=2))
        return 0 if not found else 1

    if not found:
        print(f"✅ LLM 仅用于 {', '.join(pol.get('llm_scenarios') or ['prose'])}；"
              f"其余保持确定性")
        return 0
    print(f'LLM 使用越界 {len(found)} 处：')
    for item in found:
        print(f"  {item['file']}（{item['layer']} 层不应调用 LLM）")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
