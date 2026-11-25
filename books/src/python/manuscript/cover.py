#!/usr/bin/env python3
"""Update cover.md with latest stats from source files.
Run BEFORE merge.py. Reads all source files and updates
cover.md line count, figure count, and source reference count."""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import glob as _glob
import os
import re

from lib import _config, _fsutil, _mdutil

_fsutil.pin_stdout_utf8()

docs_dir = _config.BOOK_ROOT
src_dir = _config.MANUSCRIPT_DIR
dist_dir = _config.DIST_DIR

# Front matter (preface, copyright, reading guide)
front_dir = os.path.join(src_dir, 'front')
front_files = sorted(_glob.glob(os.path.join(front_dir, '*.md'))) if os.path.isdir(front_dir) else []

# Back matter (glossary, references, index)
back_dir = os.path.join(src_dir, 'back')
back_files = sorted(_glob.glob(os.path.join(back_dir, '*.md'))) if os.path.isdir(back_dir) else []

# Reading order comes from book.toml (front matter + chapters + back matter).
source_files = [os.path.relpath(f, src_dir) for f in _config.all_manuscript_files()]

total_lines = 0
total_figs = 0
total_refs = 0

for fname in source_files:
    path = os.path.join(src_dir, fname)
    if not os.path.exists(path):
        continue
    text = _fsutil.read_text(path)
    lines = len(text.splitlines())
    # Numeric chapter figures: **图 7-3:**.
    figs = len(re.findall(r'^\*\*图 \d+-\d+:', text, re.MULTILINE))
    figs += len(re.findall(r'^图 \d+-\d+:', text, re.MULTILINE))
    # Appendix figures use a letter prefix: **图 A-1:**.
    figs += len(re.findall(r'^\*\*图 [A-Z]-\d+:', text, re.MULTILINE))
    figs += len(re.findall(r'^图 [A-Z]-\d+:', text, re.MULTILINE))
    refs = len(_mdutil.source_ref_re(tuple(_config.source_suffixes())).findall(text))
    total_lines += lines
    total_figs += figs
    total_refs += refs

# Read current cover.md
cover_path = _config.manuscript('cover.md')
cover = _fsutil.read_text(cover_path)

# Update the title lines: book.toml owns the book name, the cover only repeats it
_title_en = _config.project('display_title_en', _config.TITLE)
_title_zh = _config.project('display_title_zh', _config.TITLE)
if _title_en:
    cover = re.sub(r'^# .*$', f'# {_title_en}', cover, count=1, flags=re.MULTILINE)
if _title_zh:
    cover = re.sub(r'^## .*$', f'## {_title_zh}', cover, count=1, flags=re.MULTILINE)

# Update the version: book.toml is the single source, the cover only repeats it
if _config.VERSION:
    cover = re.sub(r'(版本\s+)v[\d.]+', rf'\g<1>v{_config.VERSION}', cover, count=1)

# Update the book's last-update date (git date of the manuscript, else mtime)
book_date = _config.book_updated()
if book_date:
    cover = re.sub(r'(版本\s+v[\d.]+\s+·\s+)\d{4}-\d{2}-\d{2}',
                   rf'\g<1>{book_date}', cover)

# Update line count
cover = re.sub(r'(版本\s+v[\d.]+\s+·\s+\d+-\d+-\d+\s+·\s+)[\d,]+\s+行',
               rf'\g<1>{total_lines:,} 行', cover)

# Update figures and references
cover = re.sub(r'(共[\s\S]*?·\s*)[\d,]+(\s*幅 ASCII)',
               rf'\g<1>{total_figs}\g<2>', cover)
cover = re.sub(r'(·\s*)[\d,]+(\s*处源码引用)',
               rf'\g<1>{total_refs}\g<2>', cover)

_fsutil.write_text(cover_path, cover)

print(f"✅ cover.md 更新完成: {total_lines:,} 行, {total_figs} 图, {total_refs} 引用")
