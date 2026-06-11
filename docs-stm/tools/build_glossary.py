#!/usr/bin/env python3
"""
Glossary builder for H2 documentation.

Scans all chapter files and extracts:
1. Bold terms (**TERM**) that appear to be glossary-worthy
2. First occurrence of each term to determine chapter mapping
3. Context around first occurrence to infer definition

Outputs a draft glossary.md that can be edited and refined.

Flags:
  --coverage  Output per-chapter term coverage report from existing glossary.md.
"""
import re, os, sys, glob
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

script_dir = os.path.dirname(os.path.abspath(__file__))
docs_dir = os.path.normpath(os.path.join(script_dir, '..'))
chapter_files = sorted(glob.glob(os.path.join(docs_dir, 'ch[0-9]*.md')))
glossary_path = os.path.join(docs_dir, 'back', 'glossary.md')


# ---- Coverage mode ----

if '--coverage' in sys.argv:
    # Parse glossary entries and extract chapter references
    ch_pattern = re.compile(r'第(\d+)章')
    term_pattern = re.compile(r'^- \*\*([^*]+)\*\*')
    chapter_terms: dict[int, list[str]] = {}
    total = 0

    with open(glossary_path, 'r', encoding='utf-8') as f:
        for line in f:
            m = term_pattern.match(line.strip())
            if m:
                term = m.group(1).strip()
                chapters = set(int(c) for c in ch_pattern.findall(line))
                for ch in chapters:
                    chapter_terms.setdefault(ch, []).append(term)
                total += 1

    # Determine expected chapters from the doc file set
    expected_chapters = set()
    for fpath in chapter_files:
        with open(fpath, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.match(r'^# 第(\d+)章', line)
                if m:
                    expected_chapters.add(int(m.group(1)))

    print('=== 术语表章节覆盖率 ===')
    print(f'总条目数: {total}')
    print()
    print(f'{"章节":<8} {"条目数":<8} {"状态":<12} 术语')
    print('-' * 80)
    all_ok = True
    for ch in sorted(expected_chapters):
        terms = chapter_terms.get(ch, [])
        count = len(terms)
        status = 'OK' if count >= 3 else '不足 (需≥3)'
        if count < 3:
            all_ok = False
        term_list = ', '.join(terms[:6])
        if len(terms) > 6:
            term_list += f', ... (共{count}条)'
        print(f'第{ch}章  {count:<8} {status:<12} {term_list}')

    print()
    if all_ok:
        print('结果: 所有章节均满足 ≥3 条术语。')
    else:
        print('结果: 部分章节术语不足，请补充。')
    sys.exit(0)


# ---- Default: generate glossary draft from chapter files ----

# Collect all bold terms with chapter context
term_first = {}  # term -> (chapter, line_text)
all_terms = set()

for fpath in chapter_files:
    fname = os.path.basename(fpath)
    # Extract chapter number from filename or content
    ch_num = None
    with open(fpath, 'r', encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^# 第(\d+)章', line)
            if m:
                ch_num = int(m.group(1))
                break

    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        # Extract bold terms: **EnglishTerm** or **中文术语**
        for m in re.finditer(r'\*\*([^*]+)\*\*', line):
            term = m.group(1).strip()
            if len(term) < 3:
                continue
            # Skip figure captions
            if re.match(r'^图 \d+-\d+', term):
                continue
            # Skip section markers and metadata
            if term in ('本章导读', '前置知识', '章节要点', '注意', '说明', '提示', '警告', '参考'):
                continue
            if term in ('核心文件', '源码位置', '实现位置', '延展阅读', '待补充'):
                continue
            # Skip numbered items (list markers) and code-like terms
            if re.match(r'^\d+[.、]', term):
                continue
            if re.match(r'^[a-z_]+\(', term):
                continue
            # Skip heading abbreviations (e.g. "1.1 H2 Database 概述")
            if re.match(r'^\d+\.\d+\s', term):
                continue

            all_terms.add(term)
            if term not in term_first:
                term_first[term] = (ch_num, line.strip())

# Output the glossary draft
print('# 术语表（自动生成草稿）')
print()
print('> 本书核心术语的中英文对照和简要定义。条目按字母顺序排列。')
print('> **注意**: 本文件由 build_glossary.py 自动生成，需要人工审核和补充定义。')
print()

# Sort alphabetically (case-insensitive)
sorted_terms = sorted(all_terms, key=lambda t: t.lower())

# Group by first letter
current_letter = ''
for term in sorted_terms:
    first_letter = term[0].upper()
    if first_letter != current_letter:
        current_letter = first_letter
        print(f'## {current_letter}')
        print()

    ch_num, context = term_first.get(term, ('?', ''))
    ch_info = f'（第{ch_num}章）' if ch_num else ''

    # Try to extract a definition from context
    # Look for patterns: "term：definition" or "term: definition"
    definition = ''
    # Try text after the bold term
    after_bold = re.split(r'\*\*' + re.escape(term) + r'\*\*', context, maxsplit=1)
    if len(after_bold) > 1:
        suffix = after_bold[1].strip()
        # Check for colon separator
        if suffix.startswith(':'):
            definition = suffix[1:].strip()
        elif suffix.startswith('：'):
            definition = suffix[1:].strip()
        # If definition is too long, truncate
        if len(definition) > 150:
            definition = definition[:147] + '...'

    if definition:
        print(f'- **{term}**: {definition} {ch_info}')
    else:
        print(f'- **{term}** — 待补充定义 {ch_info}')
    print()