#!/usr/bin/env python3
"""Smart audit: count diagrams per ### sub-chapter, aggregating from #### children."""
import re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

chapter_names = [
    "ch1-2-architecture.md",
    "ch3-packages.md",
    "ch4-5-modules-processes.md",
    "ch6-1-data-structures.md",
    "ch6-2-storage-algorithms.md",
    "ch6-3-query-algorithms.md",
    "ch7-8-sql-optimizer.md",
    "ch9-10-persistence-locking.md",
    "ch11-12-guide-summary.md",
]

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')
CHAPTERS = [os.path.join(docs_dir, name) for name in chapter_names]

DIAGRAM_MARKERS = ['┌', '└', '├', '│', '▼', '▲', '→']

def count_diagrams(text):
    lines = text.split('\n')
    in_block = False
    block_lines = 0
    count = 0
    for l in lines:
        has_marker = any(m in l for m in DIAGRAM_MARKERS)
        if has_marker and not in_block:
            in_block = True; block_lines = 1
        elif has_marker and in_block:
            block_lines += 1
        elif not has_marker and in_block:
            if block_lines >= 3: count += 1
            in_block = False; block_lines = 0
    if in_block and block_lines >= 3: count += 1
    return count

all_gaps = []

# Build exemption ranges: ### sections under ## 附：(appendix) headings
def build_exempt_ranges(headings, lines):
    """Return list of (start, end) line ranges that are exempt from diagram counting."""
    exempt = []
    for idx, (line_num, level, title) in enumerate(headings):
        if level == 2 and title.startswith('附：'):
            end = len(lines)
            for next_idx in range(idx + 1, len(headings)):
                if headings[next_idx][1] <= 2:
                    end = headings[next_idx][0]
                    break
            exempt.append((line_num, end))
    return exempt

for filepath in CHAPTERS:
    short = os.path.basename(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    headings = []
    for i, line in enumerate(lines):
        m = re.match(r'^(#{2,4})\s+(.+)$', line)
        if m:
            headings.append((i, len(m.group(1)), m.group(2)))

    # Build exemption ranges for appendix sub-sections
    exempt_ranges = build_exempt_ranges(headings, lines)

    # Process ### headings, aggregating #### children
    for idx, (line_num, level, title) in enumerate(headings):
        if level != 3:
            continue

        # Skip sections under appendix (## 附：) headings
        if any(start <= line_num < end_r for start, end_r in exempt_ranges):
            continue

        # Find end boundary: next heading at level <= 3 (### or ## or #)
        end = len(lines)
        for next_idx in range(idx + 1, len(headings)):
            if headings[next_idx][1] <= 3:
                end = headings[next_idx][0]
                break

        # Find direct #### children within this ### section
        child_sections = []
        for hidx, (hln, hl, ht) in enumerate(headings):
            if hl == 4 and hln > line_num and hln < end:
                h_end = end
                for nid in range(hidx + 1, len(headings)):
                    if headings[nid][0] >= end:
                        break
                    if headings[nid][1] == 4:
                        h_end = headings[nid][0]
                        break
                child_sections.append((hln, h_end, ht))

        if child_sections:
            # ### is a structural heading with #### children
            # Count diagrams in child sections
            total_diagrams = 0
            for cs, ce, ct in child_sections:
                child_text = ''.join(lines[cs:ce])
                total_diagrams += count_diagrams(child_text)
            has_children = True
        else:
            # ### is a standalone content section
            section_text = ''.join(lines[line_num:end])
            total_diagrams = count_diagrams(section_text)
            has_children = False

        section_len = end - line_num
        code_blocks = ''.join(lines[line_num:end]).count('```') // 2
        java_refs = ''.join(lines[line_num:end]).count('.java:')

        if total_diagrams < 2:
            all_gaps.append((short, title[:70], section_len, total_diagrams, code_blocks, java_refs, has_children))

print(f"\n{'='*70}")
print(f"Sections needing >=2 diagrams (aggregated from #### children)")
print(f"{'='*70}")
by_file = {}
for short, title, sl, dd, cb, jr, hc in all_gaps:
    if short not in by_file:
        by_file[short] = []
    by_file[short].append((title, sl, dd, cb, jr, hc))

total = 0
for fname, gaps in sorted(by_file.items()):
    real_gaps = [(t, sl, dd, cb, jr, hc) for t, sl, dd, cb, jr, hc in gaps if sl > 5]
    if not real_gaps:
        continue
    print(f"\n  {fname} ({len(real_gaps)} sections):")
    for title, sl, dd, cb, jr, hc in real_gaps:
        tag = " [has #### children]" if hc else ""
        needed = 2 - dd
        flag = f" <<< +{needed} diagram{'s' if needed>1 else ''}" if needed > 0 else ""
        print(f"    ### {title} ({sl}l, {dd} diag total{', cb='+str(cb) if cb else ''}){tag}{flag}")
        total += 1

print(f"\n{'='*70}")
print(f"TOTAL sections needing additional diagrams: {total}")
