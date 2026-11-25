#!/usr/bin/env python3
"""Smart audit: count diagrams per ### sub-chapter, aggregating from #### children.

Usage:
  python smart.py               # Default: section diagram coverage check
  python smart.py --fig-refs    # Figure reference consistency report
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
import re
import sys

from lib import _config, _fsutil, _mdutil

_fsutil.pin_stdout_utf8()


docs_dir = _config.BOOK_ROOT
src_dir = _config.MANUSCRIPT_DIR
dist_dir = _config.DIST_DIR
# Tolerate the appendix file being absent during phased delivery.

DEFAULT_DIAGRAM_MARKERS = ["┌", "└", "├", "│", "▼", "▲", "→"]
DIAGRAM_MARKERS = list(
    (_config.STYLE_POLICY.get("diagrams") or {}).get("markers") or DEFAULT_DIAGRAM_MARKERS
)


# --- Figure reference check (--fig-refs) ---
def _figures_in(lines: list[str]) -> list[tuple[int, str, str]]:
    """(1-based line, figure id, caption) for every caption line."""
    caption_re = _mdutil.FIGURE_CAPTION_RE
    figures = []
    for index, line in enumerate(lines):
        match = caption_re.match(line.strip())
        if match:
            figures.append((index + 1, match.group(1), match.group(2).strip()))
    return figures


def _is_referenced(
    lines: list[str], line_number: int, fig_id: str, before: int = 101, after: int = 30
) -> bool:
    """Whether the text around a caption refers to it.

    Prose points at a figure in several shapes (如图 X-Y 所示, 图 X-Y，, 图 X-Y 和 Z);
    all of them count, and the window is asymmetric because a reference usually
    precedes the caption.
    """
    start = max(0, line_number - before)
    end = min(len(lines), line_number + after)
    patterns = (
        f"如图 {fig_id} 所示",
        f"图 {fig_id} ",
        f"图 {fig_id}。",
        f"图 {fig_id}）",
        f" 和 {fig_id} ",
        f" 与 {fig_id} ",
        f"、{fig_id} ",
    )
    for index in range(start, end):
        if index + 1 == line_number:
            continue
        line = lines[index]
        if any(pattern in line for pattern in patterns):
            return True
    return False


def check_figure_refs():
    """Scan all figures, count references, report coverage per file."""
    total_figs = 0
    total_refd = 0

    print(f"\n{'=' * 70}")
    print("Figure Reference Consistency Report")
    print(f"{'=' * 70}\n")

    for filepath in _config.chapter_files(include_cover=False):
        short = os.path.basename(filepath)
        lines = _fsutil.read_lines(filepath)
        figures = _figures_in(lines)

        if not figures:
            print(f"  {short}: 0 figures")
            continue

        unreferenced = [
            (ln, fid, cap) for ln, fid, cap in figures if not _is_referenced(lines, ln, fid)
        ]
        refd_count = len(figures) - len(unreferenced)
        total_figs += len(figures)
        total_refd += refd_count

        pct = refd_count / len(figures) * 100 if figures else 0
        print(f"  {short}: {len(figures)} figures, {refd_count} referenced ({pct:.0f}%)")
        for ln, fid, cap in unreferenced:
            cap_short = cap[:60] + "…" if len(cap) > 60 else cap
            print(f"    UNREF L{ln}: 图{fid}: {cap_short}")

    overall_pct = total_refd / total_figs * 100 if total_figs else 0
    target_pct = coverage_target_pct()
    print(f"\n  {'=' * 50}")
    print(f"  TOTAL: {total_figs} figures, {total_refd} referenced ({overall_pct:.1f}%)")
    verdict = "PASS" if overall_pct >= target_pct else "NEEDS IMPROVEMENT"
    print(f"  COVERAGE: {verdict} (target >= {target_pct}%)")


# --- Diagram counting ---
def count_diagrams(text):
    lines = text.split("\n")
    in_block = False
    block_lines = 0
    count = 0
    for line in lines:
        has_marker = any(m in line for m in DIAGRAM_MARKERS)
        if has_marker and not in_block:
            in_block = True
            block_lines = 1
        elif has_marker and in_block:
            block_lines += 1
        elif not has_marker and in_block:
            if block_lines >= 3:
                count += 1
            in_block = False
            block_lines = 0
    if in_block and block_lines >= 3:
        count += 1
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
        level == 1 and title.lstrip().startswith("附录") for _, level, title in headings
    )
    if file_is_appendix and headings:
        return [(0, len(lines))]
    for idx, (line_num, level, title) in enumerate(headings):
        if level == 2 and title.startswith("附："):
            end = len(lines)
            for next_idx in range(idx + 1, len(headings)):
                if headings[next_idx][1] <= 2:
                    end = headings[next_idx][0]
                    break
            exempt.append((line_num, end))
    return exempt


# --- Main ---
def quality_policy() -> dict:
    """The figure floors this book declares, read when asked."""
    return _config.STYLE_POLICY.get("quality") or {}


def min_figures() -> int:
    return int(quality_policy().get("min_figures_per_section", 2))


def coverage_target_pct() -> int:
    return int(quality_policy().get("min_figure_coverage_pct", 95))


if __name__ == "__main__":
    if "--fig-refs" in sys.argv:
        check_figure_refs()
        sys.exit(0)

    all_gaps = []

    for filepath in _config.chapter_files(include_cover=False):
        short = os.path.basename(filepath)
        lines = _fsutil.read_lines(filepath)

        headings = []
        for i, line in enumerate(lines):
            # Include H1 so build_exempt_ranges can detect appendix files
            # whose top-level heading is `# 附录 …`.
            m = re.match(r"^(#{1,4})\s+(.+)$", line)
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
                    # `end` is the first heading at level <= 3 after this section, so any
                    # heading in between is level 4: the next one closes the child
                    nxt = headings[hidx + 1][0] if hidx + 1 < len(headings) else end
                    child_sections.append((hln, min(nxt, end), ht))

            if child_sections:
                total_diagrams = 0
                for cs, ce, _ct in child_sections:
                    child_text = "".join(lines[cs:ce])
                    total_diagrams += count_diagrams(child_text)
                has_children = True
            else:
                section_text = "".join(lines[line_num:end])
                total_diagrams = count_diagrams(section_text)
                has_children = False

            section_len = end - line_num
            code_blocks = "".join(lines[line_num:end]).count("```") // 2
            refs = _mdutil.source_ref_re(tuple(_config.source_suffixes()))
            source_refs = len(refs.findall("".join(lines[line_num:end])))

            if total_diagrams < min_figures():
                all_gaps.append(
                    (
                        short,
                        title[:70],
                        section_len,
                        total_diagrams,
                        code_blocks,
                        source_refs,
                        has_children,
                    )
                )

    print(f"\n{'=' * 70}")
    print(f"Sections needing >={min_figures()} diagrams (aggregated from #### children)")
    print(f"{'=' * 70}")
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
        for title, sl, dd, cb, _jr, hc in real_gaps:
            tag = " [has #### children]" if hc else ""
            needed = 2 - dd
            flag = f" <<< +{needed} diagram{'s' if needed > 1 else ''}" if needed > 0 else ""
            print(
                f"    ### {title} ({sl}l, {dd} diag total{', cb=' + str(cb) if cb else ''}){tag}{flag}"
            )
            total += 1

    print(f"\n{'=' * 70}")
    print(f"TOTAL sections needing additional diagrams: {total}")
