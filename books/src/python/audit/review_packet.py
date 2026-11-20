#!/usr/bin/env python3
"""Build a scoped review packet: only the failures, only the lines around them.

The manuscript is several megabytes; a review that reads it whole burns tokens on
text that already passes every gate. This command runs the JSON-capable gates,
keeps the failing items, and emits a compact packet with a few lines of context
around each failure — the unit an LLM (or a reviewer) actually needs.

Nothing here decides anything: the gates already decided. The packet only makes
the decision cheap to act on.

Usage:
  python review_packet.py > books/logs/review-packet.md
  python review_packet.py --json             # summary only (counts per gate)
  python review_packet.py --gates content_depth,structure --context 3
  python review_packet.py --max-bytes 60000  # cap the packet size
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil, _log

LOG = _log.get_logger('review_packet')
TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DIR = os.path.join(TOOLS_DIR, 'audit')
DEFAULT_GATES = ('content_depth', 'structure', 'captions', 'style_rules')

# gate -> the JSON keys that carry individual findings
FINDING_KEYS = ('problems', 'findings', 'violations', 'issues')


def run_gate(name: str) -> list[dict]:
    """Run one gate with --json and return its findings as flat records.

    A gate that passes contributes nothing: its accepted backlog is already
    reviewed, and shipping it in the packet would only dilute the failures.
    """
    path = os.path.join(AUDIT_DIR, f'{name}.py')
    if not os.path.exists(path):
        return []
    proc = subprocess.run([sys.executable, path, '--json'], cwd=TOOLS_DIR,
                          capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return []
    if not proc.stdout.strip():
        LOG.debug('gate %s produced no JSON (rc=%s)', name, proc.returncode)
        return []
    text = proc.stdout[proc.stdout.find('{'):] if '{' in proc.stdout else ''
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Some gates are aggregate reports without a JSON schema; their FAIL
        # lines are still actionable, so keep them as plain findings.
        return [{'gate': name, 'message': line.strip()[len('FAIL: '):]}
                for line in proc.stdout.splitlines() if line.strip().startswith('FAIL:')]
    records: list[dict] = []
    items = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        for key in FINDING_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                items = items + value
    for item in items:
        if isinstance(item, str):
            records.append({'gate': name, 'message': item})
        elif isinstance(item, dict):
            records.append({'gate': name, **item})
    return records


def locate(record: dict) -> tuple[str | None, int | None]:
    """(relative manuscript path, line) for a finding, best effort."""
    name = record.get('file') or record.get('path')
    line = record.get('line') or record.get('lineno')
    if not name:
        return None, None
    base = name if os.path.isabs(name) else None
    for root in (_config.MANUSCRIPT_DIR, _config.BOOK_ROOT):
        candidate = base or os.path.join(root, name)
        if os.path.exists(candidate):
            return os.path.relpath(candidate, _config.BOOK_ROOT).replace(os.sep, '/'), line
    return None, line


def excerpt(path: str, line: int | None, context: int) -> str:
    if line is None:
        return ''
    lines = _fsutil.read_lines(os.path.join(_config.BOOK_ROOT, path))
    start = max(1, line - context)
    end = min(len(lines), line + context)
    out = []
    for number in range(start, end + 1):
        marker = '>' if number == line else ' '
        out.append(f'{marker}{number:>6}| {lines[number - 1][:200]}')
    return '\n'.join(out)


def build(gates: tuple[str, ...], context: int, max_bytes: int) -> str:
    records: list[dict] = []
    for gate in gates:
        records += run_gate(gate)
    if not records:
        return '# 复核包\n\n门禁全部通过，无需复核。\n'
    grouped: dict[str, list[dict]] = {}
    unplaced: list[dict] = []
    for record in records:
        path, line = locate(record)
        if path is None:
            unplaced.append(record)
            continue
        grouped.setdefault(path, []).append({**record, 'line': line})
    chunks: list[str] = []
    size = 0
    chunks.append(f'# 复核包\n\n门禁失败 {len(records)} 项，按文件归并。'
                  f'每项只带 {context} 行上下文。\n')
    for path in sorted(grouped):
        items = grouped[path]
        section = [f'\n## {path}（{len(items)} 项）\n']
        for record in items:
            summary = record.get('message') or record.get('detail') or ''
            section.append(f"\n- [{record['gate']}] {record.get('kind', '')} "
                           f"L{record.get('line')}: {str(summary)[:160]}\n")
            body = excerpt(path, record.get('line'), context)
            if body:
                section.append(f'\n```\n{body}\n```\n')
        text = ''.join(section)
        if size + len(text) > max_bytes:
            chunks.append('\n> 已达 --max-bytes 上限，其余文件未纳入；'
                          '收紧 --gates 或调大上限。\n')
            break
        chunks.append(text)
        size += len(text)
    if unplaced:
        chunks.append(f'\n## 未定位到文件的发现（{len(unplaced)} 项）\n')
        for record in unplaced[:50]:
            summary = record.get('message') or record.get('detail') or ''
            chunks.append(f"- [{record['gate']}] {str(summary)[:160]}\n")
    return ''.join(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--gates', default=','.join(DEFAULT_GATES),
                        help='comma-separated gate names (audit/<name>.py)')
    parser.add_argument('--context', type=int, default=2, help='lines around a finding')
    parser.add_argument('--max-bytes', type=int, default=120000, help='packet size cap')
    parser.add_argument('--json', action='store_true',
                        help='summary counts instead of the packet')
    args = parser.parse_args(argv)

    gates = tuple(name.strip() for name in args.gates.split(',') if name.strip())
    records: list[dict] = []
    for gate in gates:
        records += run_gate(gate)
    if args.json:
        per_gate: dict[str, int] = {}
        for record in records:
            per_gate[record['gate']] = per_gate.get(record['gate'], 0) + 1
        print(json.dumps({'total': len(records), 'per_gate': per_gate},
                         ensure_ascii=False, indent=2))
        return 0
    # The packet goes to stdout: the audit layer reads files, it never writes.
    print(build(gates, args.context, args.max_bytes), end='')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
