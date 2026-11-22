#!/usr/bin/env python3
"""Reject process/history traces in documentation and code comments.

One purpose: the repository may not narrate how it got here. No review rounds,
no "batch N", no dated iteration logs, no completed-work ledgers, no "migrated
from" notes. Version history belongs to `changelog.md` and nowhere else.

Scope is chosen per run, so one gate answers "where do we look?":

  --kind docs   docs/**/*.md, books/README.md, CLAUDE.md (changelog.md exempt)
  --kind code   every comment line under books/src/, books/scripts/, .githooks/,
                .github/ and the comment blocks of data/tmpl and data/config — a
                repository narrates itself in shell hooks and YAML too
  --kind all    both scopes (default)

Usage:
  python traces.py                 # both scopes
  python traces.py --kind docs     # documentation only
  python traces.py --kind code --json

Exit codes: 0 clean, 1 traces found, 2 usage error.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

# Files that legitimately carry history.
EXEMPT_DOCS = ('changelog.md',)

# Documentation patterns: the language of a process log.
DOC_TRACES: tuple[tuple[str, str], ...] = (
    ('review-round', r'第\s*\d+\s*轮|R\d+\s*[-－]\s*\d+|轮次'),
    ('retrospective', r'复盘|回顾会|评审记录|评审发现'),
    ('batch', r'第\s*\d+\s*批|批\s*\d+|batch\s*\d+'),
    ('dated-plan-ref', r'2026-\d{2}-\d{2}-\d{3}'),
    ('ledger', r'已完成清单|遗留问题|未闭环|TODO\s*[（(]历史'),
    ('relative-time', r'本次(?:迭代|改动|提交)|上一轮|本轮|目前已完成'),
    ('phase-label', r'Phase [A-H]\b|第[0-9一二三四五六七八九十]+轮|演进史|里程碑'),
    ('task-id', r'(?<![\w-])(?:rf|plan)-\d+'),
)

# Code patterns: comments explaining which round produced the code.
CODE_TRACES: tuple[tuple[str, str], ...] = (
    ('review-round', r'第\s*\d+\s*轮|round\s*\d+|R\d+\s*[-－]\s*\d+'),
    ('retrospective', r'复盘|评审记录|评审发现'),
    ('batch', r'第\s*\d+\s*批|batch\s*\d+'),
    ('relative-time', r'本次(?:迭代|改动|提交)|上一轮|本轮|新加的|临时绕过'),
    ('phase-label', r'Phase [A-H]\b|第[0-9一二三四五六七八九十]+轮'),
    ('migration-note', r'迁移自|由.{0,12}迁移|旧版本时|以前是'),
    ('task-id', r'(?<![\w-])(?:rf|plan)-\d+'),
)

# Files whose job is to track work: they own the ids and may cite them.
ID_OWNERS = ('plan.md', 'review-findings.md')


def doc_files() -> list[str]:
    """Documentation and repository-level guides (manuscript and dist are content)."""
    files = glob.glob(os.path.join(_config.BOOK_ROOT, 'docs', '**', '*.md'), recursive=True)
    files.append(os.path.join(_config.BOOK_ROOT, 'README.md'))
    files.append(os.path.join(_config.BOOK_ROOT, '..', 'CLAUDE.md'))
    return sorted({os.path.normpath(p) for p in files if os.path.isfile(p)})


def code_patterns() -> tuple[str, ...]:
    """Sources, configuration and launchers; paths come from the config."""
    book_dir = os.path.dirname(_config.CONFIG_PATH)
    return (
        os.path.join(_config.BOOK_ROOT, 'src', '**', '*.py'),
        os.path.join(_config.BOOK_ROOT, 'scripts', '*.sh'),
        os.path.join(_config.BOOK_ROOT, 'scripts', '*.ps1'),
        os.path.join(book_dir, '*.toml'),
        os.path.join(_config.template_dir(), '*.toml'),
        os.path.join(_config.CONFIG_DIR, '*.json'),
    )


def code_files() -> list[str]:
    """Sources and configuration, plus the hooks and CI that govern them."""
    files: list[str] = []
    for pattern in code_patterns():
        files += glob.glob(pattern, recursive=True)
    repo_root = os.path.dirname(_config.BOOK_ROOT)
    for pattern in ('.githooks/*', '.github/workflows/*'):
        files += glob.glob(os.path.join(repo_root, pattern))
    return sorted(set(files))


def comment_lines(text: str) -> list[tuple[int, str]]:
    """(line number, stripped text) for every comment or docstring line."""
    out: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.split('\n'), start=1):
        stripped = line.strip()
        if stripped.startswith(('#', '*', '//', ';')) or '"""' in line:
            out.append((lineno, stripped))
    return out


def scan_docs() -> list[dict]:
    findings = []
    for path in doc_files():
        if any(path.endswith(name) for name in EXEMPT_DOCS):
            continue
        owner = os.path.basename(path) in ID_OWNERS
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            for kind, pattern in DOC_TRACES:
                if kind == 'task-id' and owner:
                    continue
                if re.search(pattern, line):
                    findings.append(_finding(path, lineno, kind, line))
    return findings


def config_notes(path: str) -> list[tuple[int, str]]:
    """Comment-equivalent lines of a JSON config: the `_note`/`_comment` values."""
    notes: list[tuple[int, str]] = []
    raw = _fsutil.read_lines(path)
    for lineno, line in enumerate(raw, start=1):
        stripped = line.strip()
        if stripped.startswith(('"_note"', '"_comment"')):
            notes.append((lineno, stripped))
    return notes


def scan_code() -> list[dict]:
    findings = []
    for path in code_files():
        if path.endswith('.json'):
            for lineno, line in config_notes(path):
                for kind, pattern in CODE_TRACES:
                    if re.search(pattern, line):
                        findings.append(_finding(path, lineno, kind, line))
            continue
        fixture = os.sep + 'test' + os.sep in path
        for lineno, line in comment_lines(_fsutil.read_text(path)):
            for kind, pattern in CODE_TRACES:
                if kind == 'task-id' and fixture:
                    continue  # tests cite ids on purpose: they are the fixtures
                if re.search(pattern, line):
                    findings.append(_finding(path, lineno, kind, line))
    return findings


def _finding(path: str, lineno: int, kind: str, text: str) -> dict:
    return {'file': os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..')),
            'line': lineno, 'kind': kind, 'text': text.strip()[:120]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--kind', choices=('docs', 'code', 'all'), default='all',
                        help='which scope to scan (default: all)')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    findings: list[dict] = []
    if args.kind in ('docs', 'all'):
        findings += scan_docs()
    if args.kind in ('code', 'all'):
        findings += scan_code()

    if args.json:
        print(json.dumps({'kind': args.kind, 'count': len(findings),
                          'findings': findings}, ensure_ascii=False, indent=2))
        return 0 if not findings else 1

    label = {'docs': '文档', 'code': '代码注释', 'all': '文档与代码'}[args.kind]
    if not findings:
        print(f'✅ {label}无历史痕迹')
        return 0
    print(f'{label}历史痕迹 {len(findings)} 处：')
    for item in findings[:40]:
        print(f"  {item['file']}:{item['line']}  [{item['kind']}] {item['text']}")
    return 1


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
