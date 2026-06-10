#!/usr/bin/env python3
"""
Add glossary reference note to each chapter's guide block.

Inserts a standardized line into each chapter's existing guide block
(> **本章导读** section) referencing the book-end glossary.
"""
import re, os, glob

script_dir = os.path.dirname(os.path.abspath(__file__))
docs_dir = os.path.normpath(os.path.join(script_dir, '..'))

chapter_files = sorted(glob.glob(os.path.join(docs_dir, 'ch[0-9]*.md')))
glossary_ref = '> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。\n'
count = 0

for fpath in chapter_files:
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    if '术语参考' in content:
        print(f"  Already annotated: {os.path.basename(fpath)}")
        continue

    # Find the guide block end: look for "章节要点:" line followed by a non-quote line
    # Insert after the last > line in the guide block
    lines = content.split('\n')
    last_guide_line = -1
    in_guide = False
    for i, line in enumerate(lines):
        if line.strip().startswith('> **本章导读**'):
            in_guide = True
        if in_guide and line.strip().startswith('>'):
            last_guide_line = i
        elif in_guide and not line.strip().startswith('>') and line.strip() != '':
            break

    if last_guide_line >= 0:
        lines.insert(last_guide_line + 1, glossary_ref.rstrip('\n'))
        content = '\n'.join(lines)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        count += 1
        print(f"  Added to {os.path.basename(fpath)}")
    else:
        print(f"  No guide block found: {os.path.basename(fpath)}")

print(f"Updated {count} chapter files")