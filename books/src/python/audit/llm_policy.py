#!/usr/bin/env python3
"""Enforce where the LLM may be used ("用在刀刃上").

Policy (data/config/llm_settings.json -> policy):
- prose scenarios may call the LLM (chapter-draft, chapter-polish, summary,
  review), including ingest's lead-in/summary when `book.toml [llm].ingest_prose`
  (or `--llm`) switches it on;
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
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_LAYERS = ('core', 'ingest')
IMPORT_RE = re.compile(r'^\s*(?:from\s+lib\s+import\s+[^\n]*\b_llm\b|import\s+lib\._llm)', re.MULTILINE)


def policy() -> dict:
    try:
        return json.loads(_fsutil.read_text(
            os.path.join(_config.BOOK_ROOT, 'data', 'config', 'llm_settings.json'))
        ).get('policy') or {}
    except (OSError, json.JSONDecodeError):
        return {}


SECRET_NAME = os.path.basename(_config.key_file())


def secret_files() -> list[str]:
    """Key files that git tracks, plus an example file that holds a value."""
    problems: list[str] = []
    try:
        listed = subprocess.run(['git', 'ls-files', '--', f'*{SECRET_NAME}', '*llm_key*'],
                                capture_output=True, text=True, timeout=20, check=False,
                                cwd=_config.BOOK_ROOT)
    except (OSError, subprocess.SubprocessError):
        return problems
    for line in listed.stdout.splitlines():
        rel = line.strip()
        if rel and rel.endswith(SECRET_NAME):
            problems.append(f'{rel}: a key file is tracked by git (remove it, rotate the key)')

    example = os.path.join(_config.BOOK_ROOT, 'data', 'config', 'llm_key.example.json')
    if os.path.exists(example):
        try:
            data = json.loads(_fsutil.read_text(example))
        except json.JSONDecodeError:
            problems.append('llm_key.example.json: invalid JSON')
            data = {}
        for name, value in (data.get('keys') or {}).items():
            if str(value).strip():
                problems.append(f'llm_key.example.json: keys.{name} is filled in; '
                                'the example must stay empty')
    return problems


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
    leaks = secret_files()

    if args.json:
        print(json.dumps({'policy': pol, 'offenders': found, 'secret_files': leaks},
                         ensure_ascii=False, indent=2))
        return 0 if not found and not leaks else 1

    if leaks:
        print(f'密钥文件不合规 {len(leaks)} 处：')
        for item in leaks:
            print(f'  {item}')
        return 1

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
