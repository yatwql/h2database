#!/usr/bin/env python3
"""Audit cross-reference accuracy: check every `详见第X章《...》` pattern."""
import re, os, glob

docs_dir = 'docs-stm'
chapter_files = sorted(glob.glob(os.path.join(docs_dir, 'ch[0-9]*.md')))

# Extract all H1 titles
h1_map = {}
for f in chapter_files:
    with open(f, 'r', encoding='utf-8') as fh:
        for line in fh:
            m = re.match(r'^# 第(\d+)章\s+(.+)$', line.strip())
            if m:
                ch_num = int(m.group(1))
                title = m.group(2).strip()
                h1_map[ch_num] = (title, os.path.basename(f))

print('=== Chapter H1 Titles ===')
for ch in sorted(h1_map):
    title, fname = h1_map[ch]
    print(f'  ch{ch}: "{title}" ({fname})')

# Extract all `详见第X章《...》` references
cross_refs = []
for f in sorted(glob.glob(os.path.join(docs_dir, 'ch*.md'))):
    fname = os.path.basename(f)
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    for m in re.finditer(r'详见第(\d+)章《([^》]+)》', content):
        cross_refs.append((fname, m.group(1), m.group(2), m.start()))

print(f'\n=== Cross-References Found: {len(cross_refs)} ===')
errors = []
ok_count = 0
for fname, ref_ch, ref_title, pos in cross_refs:
    ch_num = int(ref_ch)
    if ch_num in h1_map:
        actual_title = h1_map[ch_num][0]
        if ref_title == actual_title:
            ok_count += 1
        else:
            errors.append((fname, ref_ch, ref_title, actual_title, pos))
    else:
        errors.append((fname, ref_ch, ref_title, 'CHAPTER_NOT_FOUND', pos))

if errors:
    print(f'\n=== MISMATCHES: {len(errors)} ===')
    for fname, ref_ch, ref_title, actual_title, pos in errors:
        print(f'  {fname}: ch{ref_ch} ref "{ref_title}" -> actual "{actual_title}"')
else:
    print('\n=== All cross-references match! ===')

print(f'\nOK: {ok_count}, Errors: {len(errors)}')