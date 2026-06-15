#!/usr/bin/env python3
"""Smart audit: count diagrams per ### sub-chapter, aggregating from #### children.

Usage:
  python _audit_smart.py               # Default: section diagram coverage check
  python _audit_smart.py --fig-refs    # Figure reference consistency report
"""
import re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

chapter_names = [
    "ch1-2-architecture.md",
    "ch3-packages.md",
    "ch4-5-modules-processes.md",
    "ch6-1-data-structures.md",
    "ch6-2-storage-algorithms.md",
    "ch6-3-query-algorithms.md",
    "ch7-sql-execution.md",
    "ch8-query-optimizer.md",
    "ch9-10-persistence-locking.md",
    "ch11-12-guide-summary.md",
    # v5.4 — Phase D end-to-end case studies appendix.
    "appendix-a-case-studies.md",
]

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')
CHAPTERS = [os.path.join(docs_dir, name) for name in chapter_names]
# Tolerate the appendix file being absent during phased delivery.
CHAPTERS = [p for p in CHAPTERS if os.path.exists(p)]

DIAGRAM_MARKERS = ['┌', '└', '├', '│', '▼', '▲', '→']

# --- Figure reference check (--fig-refs) ---
def check_figure_refs():
    """Scan all figures, count references, report coverage per file."""
    # Accepts both numeric (7-3) and appendix-style (A-1) figure IDs.
    CAPTION_RE = re.compile(r'^\*\*图 ([A-Z0-9]+-\d+[a-z]*):(.+?)\*\*$')
    total_figs = 0
    total_refd = 0

    print(f"\n{'='*70}")
    print(f"Figure Reference Consistency Report")
    print(f"{'='*70}\n")

    for filepath in CHAPTERS:
        short = os.path.basename(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        figures = []  # (line_num_1idx, fig_id, caption)
        for i, line in enumerate(lines):
            m = CAPTION_RE.match(line.strip())
            if m:
                figures.append((i + 1, m.group(1), m.group(2).strip()))

        if not figures:
            print(f"  {short}: 0 figures")
            continue

        refd_count = 0
        unreferenced = []

        for ln, fid, cap in figures:
            found = False
            start = max(0, ln - 101)
            end = min(len(lines), ln + 30)
            for j in range(start, end):
                if j + 1 == ln:
                    continue
                l = lines[j]
                # Check various reference patterns
                if '如图 ' + fid + ' 所示' in l:
                    found = True
                    break
                # Check "图 X-Y " (with any trailing context: space, 和, 与, 、, etc.)
                if ('图 ' + fid + ' ') in l or ('图 ' + fid + '。') in l or ('图 ' + fid + '）') in l or ('图 ' + fid + '\n') in l:
                    found = True
                    break
                # Check combined refs: "图 X-Y 和 Z", "X-Y 与 Z" (fig ID after 和/与)
                if (' 和 ' + fid + ' ') in l or (' 与 ' + fid + ' ') in l or ('、' + fid + ' ') in l:
                    found = True
                    break
            if found:
                refd_count += 1
            else:
                unreferenced.append((ln, fid, cap))

        total_figs += len(figures)
        total_refd += refd_count
        pct = refd_count / len(figures) * 100 if figures else 0
        print(f"  {short}: {len(figures)} figures, {refd_count} referenced ({pct:.0f}%)")
        for ln, fid, cap in unreferenced:
            cap_short = cap[:60] + '…' if len(cap) > 60 else cap
            print(f"    UNREF L{ln}: 图{fid}: {cap_short}")

    overall_pct = total_refd / total_figs * 100 if total_figs else 0
    print(f"\n  {'='*50}")
    print(f"  TOTAL: {total_figs} figures, {total_refd} referenced ({overall_pct:.1f}%)")
    print(f"  COVERAGE: {'PASS (>= 95%)' if overall_pct >= 95 else 'NEEDS IMPROVEMENT (< 95%)'}")

# --- Diagram counting ---
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

# --- Build exemption ranges for ## 附：(appendix) headings ---
def build_exempt_ranges(headings, lines):
    """Return list of (start, end) line ranges exempt from diagram counting.

    Two flavours of exemption:
      1. `## 附：…` sub-section inside a regular chapter (in-chapter appendix).
      2. v5.4 端到端案例研究附录: the file's H1 is `# 附录 …`, in which case
         the entire file is narrative — case studies legitimately reuse
         existing chapter figures via §X.Y back-refs and don't need fresh
         diagrams in every ### subsection. Skip the whole file.
    """
    exempt = []
    file_is_appendix = any(
        level == 1 and title.lstrip().startswith('附录')
        for _, level, title in headings
    )
    if file_is_appendix and headings:
        return [(0, len(lines))]
    for idx, (line_num, level, title) in enumerate(headings):
        if level == 2 and title.startswith('附：'):
            end = len(lines)
            for next_idx in range(idx + 1, len(headings)):
                if headings[next_idx][1] <= 2:
                    end = headings[next_idx][0]
                    break
            exempt.append((line_num, end))
    return exempt

# --- Main ---
if __name__ == '__main__':
    if '--fig-refs' in sys.argv:
        check_figure_refs()
        sys.exit(0)

    all_gaps = []

    for filepath in CHAPTERS:
        short = os.path.basename(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        headings = []
        for i, line in enumerate(lines):
            # Include H1 so build_exempt_ranges can detect appendix files
            # whose top-level heading is `# 附录 …`.
            m = re.match(r'^(#{1,4})\s+(.+)$', line)
            if m:
                headings.append((i, len(m.group(1)), m.group(2)))

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
                total_diagrams = 0
                for cs, ce, ct in child_sections:
                    child_text = ''.join(lines[cs:ce])
                    total_diagrams += count_diagrams(child_text)
                has_children = True
            else:
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
