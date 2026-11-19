#!/usr/bin/env python3
"""Six-dimension release scorecard.

Aggregates the existing gates and metrics into one number per dimension so the
review loop has a single, comparable target:

  功能   功能完备度（入口、语言、LLM、版本、门禁覆盖面）
  稳定   测试与可复现性（测试数、通过率、构建幂等）
  交互   入口一致性与自述（status/settings/README 索引）
  代码   静态质量（ruff、文件规模、分层、脚本契约）
  文档风格 文风评分（prose composite）
  文档质量 出版级内容指标（坐标密度、章节长度、表格、图注、链接）

Usage:
  python scorecard.py            # table + total
  python scorecard.py --json
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
REPO_ROOT = os.path.normpath(os.path.join(_config.BOOK_ROOT, '..'))
PY_REL = os.path.relpath(PY_ROOT, REPO_ROOT).replace(os.sep, '/')
TEST_REL = os.path.relpath(os.path.join(_config.BOOK_ROOT, 'src', 'test'),
                           REPO_ROOT).replace(os.sep, '/')


def _run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def _pct(value: float) -> int:
    return max(0, min(100, round(value)))


def feature_score() -> tuple[int, list[str]]:
    notes = []
    points = 0
    checks = [
        ('cli', os.path.isfile(os.path.join(PY_ROOT, 'app', 'cli.py'))),
        ('tui', os.path.isfile(os.path.join(PY_ROOT, 'app', 'tui.py'))),
        ('web', os.path.isfile(os.path.join(PY_ROOT, 'app', 'web.py'))),
        ('llm', os.path.isfile(os.path.join(PY_ROOT, 'lib', '_llm.py'))),
        ('languages', len(glob.glob(os.path.join(PY_ROOT, 'ingest', 'languages',
                                                 '[!_]*.py'))) >= 3),
        ('versions', os.path.isfile(os.path.join(PY_ROOT, 'lib', '_version.py'))),
        ('settings', os.path.isfile(os.path.join(PY_ROOT, 'app', 'settings.py'))),
    ]
    for name, ok in checks:
        points += 1 if ok else 0
        if not ok:
            notes.append(f'missing {name}')
    return _pct(100 * points / len(checks)), notes


def stability_score() -> tuple[int, list[str]]:
    notes: list[str] = []
    code, out = _run([sys.executable, '-m', 'unittest', 'discover',
                      '-s', os.path.join(_config.BOOK_ROOT, 'src', 'test'),
                      '-t', os.path.join(_config.BOOK_ROOT, 'src', 'test')])
    match = re.search(r'Ran (\d+) tests?', out)
    total = int(match.group(1)) if match else 0
    score = 100 if code == 0 else 40
    if total < 100:
        score = min(score, 70)
        notes.append(f'only {total} tests')
    if code != 0:
        notes.append('test suite failing')
    return _pct(score), notes


def interaction_score() -> tuple[int, list[str]]:
    notes: list[str] = []
    points = 0
    runners = ['launch.sh', 'launch.ps1', 'bk', 'bk.ps1', 'bootstrap.sh', 'bootstrap.ps1']
    present = sum(1 for name in runners
                  if os.path.isfile(os.path.join(_config.BOOK_ROOT, 'scripts', name)))
    points += 40 * present / len(runners)
    manuals = ['how-to-config.md', 'how-to-use-cli.md', 'how-to-use-tui.md',
               'how-to-use-web.md', 'faq.md']
    docs = sum(1 for name in manuals
               if os.path.isfile(os.path.join(_config.DOCS_DIR, 'manuals', name)))
    points += 30 * docs / len(manuals)
    readme = _fsutil.read_text(os.path.join(_config.BOOK_ROOT, 'README.md'))
    links = sum(1 for name in manuals if name in readme)
    points += 30 * links / len(manuals)
    if docs < len(manuals):
        notes.append('manual pages missing')
    if links < len(manuals):
        notes.append('README does not link every manual')
    return _pct(points), notes


def code_score() -> tuple[int, list[str]]:
    notes: list[str] = []
    code, _out = _run(['uvx', 'ruff', 'check', PY_REL, TEST_REL])
    points = 50 if code == 0 else 20
    if code != 0:
        notes.append('ruff findings')
    gate_code, _gate_out = _run([sys.executable, os.path.join(PY_ROOT, 'make.py'), 'check',
                                 '--only', 'architecture,script_contract,file_length'])
    if gate_code == 0:
        points += 50
    else:
        notes.append('architecture/contract gates failing')
    return _pct(points), notes


def _json_metric(script: str, key: str) -> float:
    path = os.path.join(PY_ROOT, 'audit', script)
    if not os.path.isfile(path):
        return 0.0
    _code, out = _run([sys.executable, path, '--json'])
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return 0.0
    value = payload.get(key) or payload
    return float(value) if isinstance(value, (int, float)) else 0.0


def prose_score() -> tuple[int, list[str]]:
    _code, out = _run([sys.executable, os.path.join(PY_ROOT, 'audit', 'prose_quality.py'),
                      '--json'])
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return 0, ['prose report unavailable']
    composite = float(payload.get('composite', 0))
    notes = [] if composite >= 80 else [f'prose composite {composite}']
    return _pct(composite), notes


def content_score() -> tuple[int, list[str]]:
    code, out = _run([sys.executable,
                      os.path.join(PY_ROOT, 'audit', 'book_quality.py'), '--json'])
    notes: list[str] = []
    if code != 0:
        notes.append('book quality gate failing')
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return (40 if code == 0 else 20), notes or ['book quality report unavailable']
    problems = payload.get('problems') or []
    score = 100 - 12 * len(problems)
    return _pct(score), problems[:3]


DIMENSIONS = (
    ('功能', feature_score),
    ('稳定', stability_score),
    ('交互', interaction_score),
    ('代码', code_score),
    ('文档风格', prose_score),
    ('文档质量', content_score),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    rows = []
    total = 0
    for name, fn in DIMENSIONS:
        score, notes = fn()
        rows.append({'dimension': name, 'score': score, 'notes': notes})
        total += score

    total = _pct(total / len(rows))
    if args.json:
        print(json.dumps({'total': total, 'dimensions': rows},
                         ensure_ascii=False, indent=2))
        return 0

    print('=' * 66)
    print(f'发布质量评分  综合 {total}/100')
    print('=' * 66)
    for row in rows:
        bar = '#' * int(row['score'] / 5)
        print(f"  {row['dimension']:<8} {row['score']:>3}  {bar}")
        for note in row['notes']:
            print(f'           - {note}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
