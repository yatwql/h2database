#!/usr/bin/env python3
"""Update cover.md with latest stats from source files.
Run BEFORE rebuild_merged.py. Reads all source files and updates
cover.md line count, figure count, and source reference count."""
import re, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')

import glob as _glob

# Front matter (preface, copyright, reading guide)
front_dir = os.path.join(docs_dir, 'front')
front_files = sorted(_glob.glob(os.path.join(front_dir, '*.md'))) if os.path.isdir(front_dir) else []

# Back matter (glossary, references, index)
back_dir = os.path.join(docs_dir, 'back')
back_files = sorted(_glob.glob(os.path.join(back_dir, '*.md'))) if os.path.isdir(back_dir) else []

source_files = ['cover.md'] + \
    [os.path.relpath(f, docs_dir) for f in front_files] + \
    ['ch1-2-architecture.md', 'ch3-packages.md',
     'ch4-5-modules-processes.md', 'ch6-1-data-structures.md',
     'ch6-2-storage-algorithms.md', 'ch6-3-query-algorithms.md',
     'ch7-sql-execution.md', 'ch8-query-optimizer.md',
     'ch9-10-persistence-locking.md',
     'ch11-12-guide-summary.md',
     # v5.4 — Phase D end-to-end case studies appendix.
     'appendix-a-case-studies.md'] + \
    [os.path.relpath(f, docs_dir) for f in back_files]

total_lines = 0
total_figs = 0
total_refs = 0

for fname in source_files:
    path = os.path.join(docs_dir, fname)
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    lines = len(text.splitlines())
    # Numeric chapter figures: **图 7-3:**.
    figs = len(re.findall(r'^\*\*图 \d+-\d+:', text, re.MULTILINE))
    figs += len(re.findall(r'^图 \d+-\d+:', text, re.MULTILINE))
    # Appendix figures use a letter prefix: **图 A-1:**.
    figs += len(re.findall(r'^\*\*图 [A-Z]-\d+:', text, re.MULTILINE))
    figs += len(re.findall(r'^图 [A-Z]-\d+:', text, re.MULTILINE))
    refs = len(re.findall(r'\.java:\d+', text))
    total_lines += lines
    total_figs += figs
    total_refs += refs

# Read current cover.md
cover_path = os.path.join(docs_dir, 'cover.md')
with open(cover_path, 'r', encoding='utf-8') as f:
    cover = f.read()

# Update line count
cover = re.sub(r'(版本\s+v[\d.]+\s+·\s+\d+-\d+-\d+\s+·\s+)[\d,]+\s+行',
               rf'\g<1>{total_lines:,} 行', cover)

# Update figures and references
cover = re.sub(r'(共[\s\S]*?·\s*)[\d,]+(\s*幅 ASCII)',
               rf'\g<1>{total_figs}\g<2>', cover)
cover = re.sub(r'(·\s*)[\d,]+(\s*处源码引用)',
               rf'\g<1>{total_refs}\g<2>', cover)

with open(cover_path, 'w', encoding='utf-8') as f:
    f.write(cover)

print(f"✅ cover.md 更新完成: {total_lines:,} 行, {total_figs} 图, {total_refs} 引用")
