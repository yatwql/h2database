#!/usr/bin/env python3
"""Readability checks for H2 analysis docs."""
from pathlib import Path
import re

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DOCS_DIR = REPO_ROOT / 'docs-stm'

DOCS = [
    DOCS_DIR / 'ch1-2-architecture.md',
    DOCS_DIR / 'ch3-packages.md',
    DOCS_DIR / 'ch4-5-modules-processes.md',
    DOCS_DIR / 'ch6-1-data-structures.md',
    DOCS_DIR / 'ch6-2-storage-algorithms.md',
    DOCS_DIR / 'ch6-3-query-algorithms.md',
    DOCS_DIR / 'ch7-8-sql-optimizer.md',
    DOCS_DIR / 'ch9-10-persistence-locking.md',
    DOCS_DIR / 'ch11-12-guide-summary.md',
]
CAPTION_RE = re.compile(r'^\*\*图 \d+-\d+:')
DIAGRAM_MARKERS = set('┌┐└┘├┤│┬┴┼')

failures = []
warnings = []

for path in DOCS:
    lines = path.read_text(encoding='utf-8').splitlines()
    in_fence = False
    fence_start = 0
    block_lines = []
    for idx, line in enumerate(lines, 1):
        if line.strip().startswith('```'):
            if not in_fence:
                in_fence = True
                fence_start = idx
                block_lines = []
            else:
                marker_lines = [l for l in block_lines if any(c in l for c in DIAGRAM_MARKERS)]
                if marker_lines:
                    max_width = max(len(l) for l in block_lines) if block_lines else 0
                    if max_width > 118:
                        warnings.append(f'{path}:{fence_start} diagram width {max_width} > 118')
                    if len(block_lines) > 80:
                        warnings.append(f'{path}:{fence_start} diagram/code block length {len(block_lines)} > 80')
                in_fence = False
            continue
        if in_fence:
            if CAPTION_RE.match(line.strip()):
                failures.append(f'{path}:{idx} caption inside fence')
            block_lines.append(line)

    if in_fence:
        failures.append(f'{path}:{fence_start} unclosed fence')

html_path = DOCS_DIR / 'h2-source-code-analysis.html'
if html_path.exists():
    html = html_path.read_text(encoding='utf-8')
    body = re.sub(r'<pre[^>]*>.*?</pre>', '', html, flags=re.S)
    lines = body.splitlines()
    outside_lines = [line for line in lines if any(c in line for c in DIAGRAM_MARKERS)]
    # Track consecutive runs of box-marker lines outside <pre>
    runs = []
    streak = 0
    for line in lines:
        if any(c in line for c in DIAGRAM_MARKERS):
            streak += 1
        else:
            if streak >= 3:
                runs.append(streak)
            streak = 0
    if streak >= 3:
        runs.append(streak)
    if runs:
        failures.append(f'{html_path}: {len(outside_lines)} diagram-like lines outside <pre>, blocks: {runs}')
    elif outside_lines:
        warnings.append(f'{html_path}: {len(outside_lines)} inline visual-aid lines use box chars outside <pre> (non-block, acceptable)')

print('READABILITY FAILURES:', len(failures))
for item in failures[:80]:
    print('FAIL:', item)
print('READABILITY WARNINGS:', len(warnings))
for item in warnings[:120]:
    print('WARN:', item)

raise SystemExit(1 if failures else 0)
