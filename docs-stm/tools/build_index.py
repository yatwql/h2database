#!/usr/bin/env python3
"""
Index builder for H2 documentation.

Scans all chapter files and extracts:
1. H3/H4 headings as potential index entries
2. Bold terms and source file references
3. Maps each entry to its chapter and section

Outputs a draft index.md that can be edited and refined.
"""
import re, os, sys, glob
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

script_dir = os.path.dirname(os.path.abspath(__file__))
docs_dir = os.path.normpath(os.path.join(script_dir, '..'))
chapter_files = sorted(glob.glob(os.path.join(docs_dir, 'ch[0-9]*.md')))

# Track section numbering across files
current_ch = 0
current_sections = []  # stack of (level, number, title)

entries = []  # (term, chapter, section_ref, type)

for fpath in chapter_files:
    fname = os.path.basename(fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Track section numbers per file
    section_counters = [0, 0, 0, 0]  # H1, H2, H3, H4

    for line in lines:
        # Track chapter change
        cm = re.match(r'^# 第(\d+)章\s+(.*)', line)
        if cm:
            current_ch = int(cm.group(1))
            section_counters = [current_ch, 0, 0, 0]
            # Add chapter as index entry
            ch_title = cm.group(2).strip()
            entries.append((ch_title, current_ch, f'第{current_ch}章', 'heading'))
            continue

        # Track H2/H3/H4 headings
        hm = re.match(r'^(#{2,4})\s+(.+)', line)
        if hm:
            level = len(hm.group(1))
            title = hm.group(2).strip()
            section_counters[level - 1] += 1
            # Reset lower-level counters
            for i in range(level, 4):
                section_counters[i] = 0

            # Build section reference like "§2.3"
            if level == 2:
                section_ref = f'§{current_ch}.{section_counters[1]}'
            elif level == 3:
                section_ref = f'§{current_ch}.{section_counters[1]}.{section_counters[2]}'
            elif level == 4:
                section_ref = f'§{current_ch}.{section_counters[1]}.{section_counters[2]}.{section_counters[3]}'
            else:
                section_ref = f'第{current_ch}章'

            entries.append((title, current_ch, section_ref, 'heading'))
            continue

        # Extract bold terms as index candidates
        for m in re.finditer(r'\*\*([^*]+)\*\*', line):
            term = m.group(1).strip()
            if len(term) < 3:
                continue
            # Skip figure captions
            if term.startswith('图 ') and ':' in term:
                continue
            # Skip metadata markers
            if term in ('注意', '说明', '提示', '警告', '参考', '核心文件', '源码位置'):
                continue
            # Build current section number
            if section_counters[1] > 0:
                sec = f'§{current_ch}.{section_counters[1]}'
                if section_counters[2] > 0:
                    sec += f'.{section_counters[2]}'
            else:
                sec = f'第{current_ch}章'
            entries.append((term, current_ch, sec, 'term'))

# Deduplicate and sort entries
seen = set()
unique_entries = []
for term, ch, sec, etype in entries:
    key = (term.lower(), ch)
    if key not in seen:
        seen.add(key)
        unique_entries.append((term, ch, sec, etype))

# Sort: alphabetical by term, then by chapter
sorted_entries = sorted(unique_entries, key=lambda e: (e[0].lower(), e[1]))

# Output the index draft
print('# 概念索引（自动生成草稿）')
print()
print('> 关键概念和术语的章节位置索引。条目按字母顺序排列。')
print('> **注意**: 本文件由 build_index.py 自动生成，需要人工审核和精简。')
print()

current_letter = ''
for term, ch, sec, etype in sorted_entries:
    first_letter = term[0].upper()
    if first_letter != current_letter:
        current_letter = first_letter
        print(f'## {current_letter}')
        print()

    if etype == 'heading':
        print(f'- **{term}** — {sec}')
    else:
        print(f'- **{term}** — {sec}')
    print()