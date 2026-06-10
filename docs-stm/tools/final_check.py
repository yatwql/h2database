#!/usr/bin/env python3
"""Comprehensive final delivery check for H2 documentation."""
import re, os, glob

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')

# Collect front/ and back/ contents (if they exist)
front_dir = os.path.join(docs_dir, 'front')
back_dir = os.path.join(docs_dir, 'back')
front_matter = sorted(glob.glob(os.path.join(front_dir, '*.md'))) if os.path.isdir(front_dir) else []
back_matter = sorted(glob.glob(os.path.join(back_dir, '*.md'))) if os.path.isdir(back_dir) else []

chapter_names = [
    'ch1-2-architecture.md',
    'ch3-packages.md',
    'ch4-5-modules-processes.md',
    'ch6-1-data-structures.md',
    'ch6-2-storage-algorithms.md',
    'ch6-3-query-algorithms.md',
    'ch7-8-sql-optimizer.md',
    'ch9-10-persistence-locking.md',
    'ch11-12-guide-summary.md',
]
CHAPTERS = front_matter + [os.path.join(docs_dir, name) for name in chapter_names] + back_matter

results = []

def check(ok, msg):
    results.append((ok, msg))
    print(f'  {"OK" if ok else "FAIL"}: {msg}')

# 1. Figure numbering - sequential per chapter
print('=== Figure Numbering ===')
# Collect all figures globally grouped by chapter
global_by_ch = {}  # ch -> [(file, base_num)]
for f in CHAPTERS:
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    figs = re.findall(r'\*\*图 (\d+)-(\d+[a-z]*):', content)
    for ch, num in figs:
        base_num = int(re.search(r'\d+', num).group())
        global_by_ch.setdefault(int(ch), []).append((f, base_num))
# Verify each chapter's figures: unique, complete, and (ideally) in-order
for ch in sorted(global_by_ch):
    entries = global_by_ch[ch]
    file_label = ', '.join(sorted(set(e[0] for e in entries)))
    nums = [e[1] for e in entries]
    unique = len(set(nums)) == len(nums)
    sorted_unique = sorted(set(nums))
    complete = sorted_unique == list(range(1, len(sorted_unique) + 1))
    in_order = nums == list(range(1, len(nums)+1))

    passed = unique and complete
    msg_parts = [f'ch{ch} ({file_label}): {len(nums)} figures']
    if not unique:
        msg_parts.append('DUPLICATE numbers found!')
    elif not complete:
        msg_parts.append(f'gaps in numbering (has {len(sorted_unique)} unique, expected {sorted_unique[-1]})')
    elif not in_order:
        out_of_order = sum(1 for a, e in zip(nums, range(1, len(nums)+1)) if a != e)
        msg_parts.append(f'all unique+complete, {out_of_order} out-of-order inserts')
    else:
        msg_parts.append('all sequential')
    check(passed, ', '.join(msg_parts))

# 2. Cross-references
print('\n=== Cross-References ===')
for f in CHAPTERS:
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    refs = re.findall(r'详见第(\d+)章', content)
    other_refs = re.findall(r'第(\d+)章[^详]', content)
    all_refs = set(int(r) for r in refs + other_refs if int(r) > 0)
    # Get current chapter number
    ch_match = re.match(r'# 第(\d+)章', content)
    curr_ch = int(ch_match.group(1)) if ch_match else 0
    # Valid refs: should reference OTHER chapters
    valid = [r for r in sorted(all_refs) if r != curr_ch]
    # Non-chapter files (front/back matter) may have zero refs
    is_chapter = bool(ch_match)
    if is_chapter and len(valid) >= 2:
        check(True, f'{f}: refs to ch{",".join(str(v) for v in valid)}')
    elif len(valid) == 1:
        check(True, f'{f}: refs to ch{valid[0]} (minimal)')
    elif is_chapter:
        check(False, f'{f}: ZERO cross-chapter refs')
    else:
        check(True, f'{f}: book front/back matter (skipped cross-ref check)')

# 3. Code fence balance
print('\n=== Code Fence Balance ===')
total_fences = 0
all_balanced = True
for f in CHAPTERS:
    with open(f, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()
    fences = sum(1 for l in lines if l.strip().startswith('```'))
    if fences % 2 != 0:
        all_balanced = False
        check(False, f'{f}: {fences} fences (ODD!)')
    else:
        check(True, f'{f}: {fences} fences (even)')
    total_fences += fences
check(all_balanced, f'Total: {total_fences} fences across all files')

# 4. Heading hierarchy
print('\n=== Heading Hierarchy ===')
for f in CHAPTERS:
    with open(f, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()
    headings = []
    for i, l in enumerate(lines):
        m = re.match(r'^(#{1,4})\s', l)
        if m:
            headings.append((len(m.group(1)), i+1, l.strip()[:60]))
    has_jump = False
    for i in range(1, len(headings)):
        if headings[i][0] - headings[i-1][0] > 1:
            check(False, f'{f}: heading jump at L{headings[i][1]} ({headings[i][0]} after {headings[i-1][0]})')
            has_jump = True
    if not has_jump:
        check(True, f'{f}: {len(headings)} headings, no level jumps')

# 5. UTF-8 encoding
print('\n=== UTF-8 Encoding ===')
for f in CHAPTERS + [os.path.join(docs_dir, 'h2-source-code-analysis.md'), os.path.join(docs_dir, 'h2-source-code-analysis.html')]:
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            fh.read()
        check(True, f'{f}: valid UTF-8')
    except UnicodeDecodeError:
        check(False, f'{f}: NOT valid UTF-8')
    except OSError as e:
        check(False, f'{f}: cannot read ({e})')

# 6. HTML TOC check
print('\n=== HTML TOC ===')
try:
    with open(os.path.join(docs_dir, 'h2-source-code-analysis.html'), 'r', encoding='utf-8') as f:
        html = f.read()
    sidebar_nav_start = html.find('<nav id="sidebar">')
    sidebar_nav_end = html.find('</nav>', sidebar_nav_start)
    content_start = html.find('<main')
    content_html = html[content_start:] if content_start >= 0 else ''
    toc_links = re.findall(r'href="#([^"]+)"', html[sidebar_nav_start:sidebar_nav_end])
    heading_ids = re.findall(r'<h[1-4]\s+id="([^"]*)"', content_html)
    heading_id_set = set(heading_ids)
    broken = [t for t in toc_links if t not in heading_id_set]
    missing = [h for h in heading_ids if h not in set(toc_links)]
    opens = len(re.findall(r'<pre><code>', html))
    closes = len(re.findall(r'</code></pre>', html))
    check(len(broken) == 0, f'TOC: {len(toc_links)} entries, {len(broken)} broken anchors')
    check(len(missing) == 0 and len(toc_links) == len(heading_ids), f'TOC/content headings: {len(toc_links)} TOC, {len(heading_ids)} headings, {len(missing)} missing from TOC')
    check(opens == closes, f'<pre><code>: {opens} open, {closes} close ({"balanced" if opens == closes else "MISMATCH"})')
except FileNotFoundError:
    check(False, 'HTML file not found')

# 7. Merged doc consistency
print('\n=== Merged Doc ===')
try:
    ALL_MD = CHAPTERS + [os.path.join(docs_dir, 'cover.md')]
    md_lines = sum(1 for f in ALL_MD for l in open(f, 'r', encoding='utf-8'))
    merged_lines = sum(1 for _ in open(os.path.join(docs_dir, 'h2-source-code-analysis.md'), 'r', encoding='utf-8'))
    check(md_lines == merged_lines, f'Chapter files (+cover): {md_lines}, Merged: {merged_lines} ({"match" if md_lines == merged_lines else "MISMATCH"})')
except FileNotFoundError:
    check(False, 'Merged doc not found')

# Summary
print(f'\n=== Summary ===')
passed = sum(1 for ok, _ in results if ok)
total = len(results)
print(f'  {passed}/{total} checks passed')
if passed < total:
    for ok, msg in results:
        if not ok:
            print(f'    FAIL: {msg}')
    raise SystemExit(1)
