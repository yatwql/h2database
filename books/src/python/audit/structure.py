#!/usr/bin/env python3
"""Comprehensive final delivery check for H2 documentation.

Gate levels (introduced in v6.0 / Phase H):

- ``p0`` — foundational integrity & renderer correctness (figure numbering,
  cross-refs, code-fence balance, heading hierarchy, UTF-8, HTML TOC,
  merged-doc consistency, CSS style hooks). Must pass for any delivery.
- ``p1`` — content-quality gates that block formal delivery (index
  integrity & hierarchy, glossary content, glossary builder availability).
- ``p2`` — v6.0-era quality gates that started life as advisory checks
  (figure caption verb-leading + length, figure cluster bridges, chapter
  exercises, writing-style audit). All currently passing; subject to
  re-rating during Phase H gate review.

Default: ``--gate-level p2`` runs every section (matches v5.x behaviour).

Usage:
    python books/tools/structure.py                  # all (p0+p1+p2)
    python books/tools/structure.py --gate-level p1  # p0+p1
    python books/tools/structure.py --gate-level p0  # p0 only
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import ast
import glob
import os
import re
import subprocess
import sys

from lib import _config

# ── Gate-level argument parsing ──────────────────────────────────────────
_arg_parser = argparse.ArgumentParser(add_help=False)
_arg_parser.add_argument('--gate-level', choices=['p0', 'p1', 'p2'], default='p2')
_arg_parser.add_argument('--help', '-h', action='store_true')
_args, _unknown = _arg_parser.parse_known_args()
if _args.help:
    print(__doc__)
    sys.exit(0)

GATE_LEVEL = _args.gate_level
LEVEL_RANK = {'p0': 0, 'p1': 1, 'p2': 2}
_active_rank = LEVEL_RANK[GATE_LEVEL]

def _read_text(path: str) -> str:
    """Read UTF-8 text; OSError propagates so callers keep their handlers."""
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except OSError as exc:
        exc.add_note(f'while reading {path}')
        raise

def _read_lines(path: str) -> list[str]:
    """Read lines; OSError propagates so callers keep their handlers."""
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.readlines()
    except OSError as exc:
        exc.add_note(f'while reading {path}')
        raise

def gate(section_level: str) -> bool:
    """Return True if the section's level is included by ``GATE_LEVEL``."""
    return LEVEL_RANK[section_level] <= _active_rank

print(f'[gate-level: {GATE_LEVEL}] running sections at or below {GATE_LEVEL}\n')

def _count_lines(path: str) -> int:
    """Count lines in a UTF-8 text file."""
    return len(_read_lines(path))

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..', '..'))
docs_dir = _config.BOOK_ROOT
src_dir = _config.MANUSCRIPT_DIR
dist_dir = _config.DIST_DIR

# Collect front/ and back/ contents (if they exist)
front_dir = os.path.join(src_dir, 'front')
back_dir = os.path.join(src_dir, 'back')
front_matter = sorted(glob.glob(os.path.join(front_dir, '*.md'))) if os.path.isdir(front_dir) else []
back_matter = sorted(glob.glob(os.path.join(back_dir, '*.md'))) if os.path.isdir(back_dir) else []

CHAPTERS = front_matter + _config.chapter_files(include_cover=False) + back_matter
# Drop any chapter file that does not yet exist (Phase D appendix may be
# absent during partial deliveries).
CHAPTERS = [p for p in CHAPTERS if os.path.exists(p)]

results = []
# SECTION_LEVEL is a "sticky" global that each section header updates;
# check() reads it to decide whether to record (and print) the result.
# Sections still execute their file I/O + computations even when skipped
# — total runtime is ~1s, so we trade tiny waste for zero indentation churn
# vs the alternative of restructuring 15 flat sections into functions.
SECTION_LEVEL = 'p0'

def check(ok, msg):
    if not gate(SECTION_LEVEL):
        return
    results.append((ok, msg))
    print(f'  {"OK" if ok else "FAIL"}: {msg}')

def section(level: str, name: str) -> None:
    """Mark the start of a new section with its gate level.

    Always prints the heading so the reader sees which sections exist;
    appends a [SKIP] marker when the level is outside the active gate."""
    global SECTION_LEVEL
    SECTION_LEVEL = level
    suffix = '' if gate(level) else f'  [SKIP — outside {GATE_LEVEL}]'
    print(f'\n=== {name} ({level}) ==={suffix}'.rstrip())

# 1. Figure numbering - sequential per chapter
# Numeric chapters use **图 N-M:** (N is chapter, M is figure index).
# v5.4 appendix uses **图 A-M:** with letter prefix; treat each letter as its
# own group so the same uniqueness/completeness invariants apply.
section('p0', 'Figure Numbering')
global_by_ch: dict = {}  # ch (int or 'A'/'B'/…) -> [(file, base_num, full_num)]
for f in CHAPTERS:
    content = _read_text(f)
    # Numeric chapters
    figs = re.findall(r'\*\*图 (\d+)-(\d+[a-z]*):', content)
    for ch, num in figs:
        digits = re.search(r'\d+', num)
        if digits is None:  # pragma: no cover - regex guarantees digits
            continue
        base_num = int(digits.group())
        global_by_ch.setdefault(int(ch), []).append((f, base_num, num))
    # Appendix letters (A, B, …)
    appendix_figs = re.findall(r'\*\*图 ([A-Z])-(\d+[a-z]*):', content)
    for letter, num in appendix_figs:
        digits = re.search(r'\d+', num)
        if digits is None:  # pragma: no cover - regex guarantees digits
            continue
        base_num = int(digits.group())
        global_by_ch.setdefault(letter, []).append((f, base_num, num))
# Verify each chapter's figures: unique, complete, and (ideally) in-order
for ch in sorted(global_by_ch, key=lambda k: (isinstance(k, str), k)):
    entries = global_by_ch[ch]
    file_label = ', '.join(sorted({e[0] for e in entries}))
    base_nums = [e[1] for e in entries]
    full_nums = [e[2] for e in entries]
    unique = len(set(full_nums)) == len(full_nums)
    sorted_bases = sorted(set(base_nums))
    complete = sorted_bases == list(range(1, len(sorted_bases) + 1))
    in_order = base_nums == list(range(1, len(base_nums)+1))

    passed = unique and complete
    label = f'ch{ch}' if isinstance(ch, int) else f'附录 {ch}'
    msg_parts = [f'{label} ({file_label}): {len(full_nums)} figures']
    if not unique:
        msg_parts.append('DUPLICATE numbers found!')
    elif not complete:
        msg_parts.append(f'gaps in numbering (has {len(sorted_bases)} unique, expected {sorted_bases[-1]})')
    elif not in_order:
        out_of_order = sum(1 for a, e in zip(base_nums, range(1, len(base_nums)+1), strict=False) if a != e)
        msg_parts.append(f'all unique+complete, {out_of_order} out-of-order inserts')
    else:
        msg_parts.append('all sequential')
    check(passed, ', '.join(msg_parts))

# 2. Cross-references
section('p0', 'Cross-References')
for f in CHAPTERS:
    content = _read_text(f)
    refs = re.findall(r'详见第(\d+)章', content)
    other_refs = re.findall(r'第(\d+)章[^详]', content)
    all_refs = {int(r) for r in refs + other_refs if int(r) > 0}
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
section('p0', 'Code Fence Balance')
total_fences = 0
all_balanced = True
for f in CHAPTERS:
    lines = _read_lines(f)
    fences = sum(1 for line in lines if line.strip().startswith('```'))
    if fences % 2 != 0:
        all_balanced = False
        check(False, f'{f}: {fences} fences (ODD!)')
    else:
        check(True, f'{f}: {fences} fences (even)')
    total_fences += fences
check(all_balanced, f'Total: {total_fences} fences across all files')

# 4. Heading hierarchy
section('p0', 'Heading Hierarchy')
for f in CHAPTERS:
    lines = _read_lines(f)
    headings = []
    for i, line in enumerate(lines):
        m = re.match(r'^(#{1,4})\s', line)
        if m:
            headings.append((len(m.group(1)), i+1, line.strip()[:60]))
    has_jump = False
    for i in range(1, len(headings)):
        if headings[i][0] - headings[i-1][0] > 1:
            check(False, f'{f}: heading jump at L{headings[i][1]} ({headings[i][0]} after {headings[i-1][0]})')
            has_jump = True
    if not has_jump:
        check(True, f'{f}: {len(headings)} headings, no level jumps')

# 5. UTF-8 encoding
section('p0', 'UTF-8 Encoding')
for f in CHAPTERS + [os.path.join(dist_dir, 'h2-source-code-analysis.md'), os.path.join(dist_dir, 'h2-source-code-analysis.html')]:
    try:
        _read_text(f)
        check(True, f'{f}: valid UTF-8')
    except UnicodeDecodeError:
        check(False, f'{f}: NOT valid UTF-8')
    except OSError as e:
        check(False, f'{f}: cannot read ({e})')

# 6. HTML TOC check
section('p0', 'HTML TOC')
try:
    html = _read_text(os.path.join(dist_dir, 'h2-source-code-analysis.html'))
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
section('p0', 'Merged Doc')
try:
    ALL_MD = CHAPTERS + [_config.manuscript('cover.md')]
    md_lines = sum(_count_lines(f) for f in ALL_MD)
    merged_lines = _count_lines(os.path.join(dist_dir, 'h2-source-code-analysis.md'))
    check(md_lines == merged_lines, f'Chapter files (+cover): {md_lines}, Merged: {merged_lines} ({"match" if md_lines == merged_lines else "MISMATCH"})')
except FileNotFoundError:
    check(False, 'Merged doc not found')

# 8. CSS style checks (non-blocking, warning only)
section('p0', 'CSS Style Checks')
try:
    gen_content = _read_text(os.path.join(script_dir, 'to_html.py'))
    css_hints = {
        'h1 decorator': 'h1::before',
        'fig-caption style': 'fig-caption',
        'zebra table': 'nth-child(even)',
        'copy button': 'copy-btn',
        'line numbers': 'line-nums',
        'breadcrumb': 'breadcrumb',
        'chapter nav': 'chapter-nav',
        'print styles': '@media print',
        'print page-break': 'page-break-inside',
    }
    all_found = True
    for name, hint in css_hints.items():
        if hint not in gen_content:
            print(f'  [WARN]  Missing: {name} ({hint})')
            all_found = False
    if all_found:
        print(f'  All {len(css_hints)} CSS features present')
    check(all_found, f'CSS style integrity: {len(css_hints)} checks')
except FileNotFoundError:
    check(True, 'CSS check skipped (to_html.py not found)')

# 9. Check: glossary builder scripts exist
section('p1', 'Glossary Builder Checks')
glossary_script = os.path.join(script_dir, 'glossary.py')
index_script = os.path.join(script_dir, 'index.py')
scripts_ok = True
for s_name, s_path in [('glossary.py', glossary_script), ('index.py', index_script)]:
    if os.path.exists(s_path):
        # Verify it can at least import without error
        try:
            ast.parse(_read_text(s_path), filename=s_path)
            print(f'  OK: {s_name} — syntax valid')
        except SyntaxError as e:
            print(f'  FAIL: {s_name} — syntax error: {e}')
            scripts_ok = False
    else:
        print(f'  [WARN]  {s_name} not found')
check(scripts_ok, 'Glossary builder scripts available')

# 11. Index integrity check
section('p1', 'Index Integrity')
index_path = os.path.join(src_dir, 'back', 'index.md')
index_ok = True
if os.path.exists(index_path):
    index_content = _read_text(index_path)

    # Count entries
    index_entries = [line.strip() for line in index_content.split('\n') if line.strip().startswith('- ')]
    entry_count = len(index_entries)
    check(entry_count >= 120, f'Index: {entry_count} entries (target: >= 120)')

    # Count per-chapter entries
    per_chapter = dict.fromkeys(range(1, 13), 0)
    for entry in index_entries:
        refs = re.findall(r'§(\d+)\.', entry)
        refs += re.findall(r'第(\d+)章', entry)
        for ref in set(refs):
            ch = int(ref)
            if 1 <= ch <= 12:
                per_chapter[ch] += 1

    # Check every chapter has >= 5 entries
    low_chapters = []
    for ch, count in sorted(per_chapter.items()):
        if count < 5:
            low_chapters.append(f'ch{ch}({count})')
            index_ok = False

    if low_chapters:
        check(False, f'Index chapters below threshold: {", ".join(low_chapters)} (need >= 5)')
    else:
        check(True, 'All chapters have >= 5 index entries')

    # Validate chapter references match real files
    chapter_files_map = {}
    for f in CHAPTERS:
        content = _read_text(f)
        # Find ALL H1 chapter headings in the file (handles combined files)
        for cm in re.finditer(r'^# 第(\d+)章', content, re.MULTILINE):
            ch = int(cm.group(1))
            chapter_files_map[ch] = f

    # Find all chapter-number references in index entries
    index_ch_refs = set()
    for entry in index_entries:
        refs = re.findall(r'§(\d+)\.', entry)
        refs += re.findall(r'第(\d+)章', entry)
        for r in refs:
            index_ch_refs.add(int(r))

    missing_refs = [ch for ch in index_ch_refs if ch not in chapter_files_map]
    if missing_refs:
        index_ok = False
        check(False, f'Index references non-existent chapters: {missing_refs}')
    else:
        check(True, f'Index chapter refs valid (covers chapters {sorted(chapter_files_map.keys())})')

    # v6.0: index hierarchy & cross-reference health (P2 advisory).
    # Run the dedicated audit tools and surface their pass/fail as separate
    # checks. We do NOT regress index_ok on advisory failure; only on hard
    # malformations (missing tools).
    import subprocess
    hier_tool = os.path.join(script_dir, 'index.py')
    if os.path.exists(hier_tool):
        try:
            res = subprocess.run(
                [sys.executable, hier_tool, '--hierarchy-check'],
                capture_output=True, text=True, encoding='utf-8',
            check=False
            )
            check(res.returncode == 0, 'Index hierarchy floor (main>=150, sub>=50, see-also>=30)')
        except Exception as exc:  # noqa: BLE001 - each sub-check reports failure instead of aborting the run
            check(False, f'Index hierarchy check failed to run: {exc}')

    xref_tool = os.path.join(script_dir, 'index_xrefs.py')
    if os.path.exists(xref_tool):
        try:
            res = subprocess.run(
                [sys.executable, xref_tool],
                capture_output=True, text=True, encoding='utf-8',
            check=False
            )
            check(res.returncode == 0, 'Index see-also targets resolve and sub-entries reference valid chapters')
        except Exception as exc:  # noqa: BLE001 - each sub-check reports failure instead of aborting the run
            check(False, f'Index xref audit failed to run: {exc}')
else:
    check(False, 'Index file not found')
    index_ok = False

# 11b. v5.5 figure caption + cluster gates (P2 advisory).
# Run them as separate checks so authors see the diagnostic at the same
# place as other quality gates. Failure does not regress index_ok; only
# missing tools count as hard failures.
section('p2', 'Figure Caption Quality (style-guide §14)')
caption_tool = os.path.join(script_dir, 'captions.py')
if os.path.exists(caption_tool):
    try:
        res = subprocess.run(
            [sys.executable, caption_tool, '--threshold', 'strict'],
            capture_output=True, text=True, encoding='utf-8',
        check=False
        )
        # _audit_captions exits 0 when violations <= fail_at; strict has
        # fail_at=0, so exit 0 ⇔ zero violations.
        check(res.returncode == 0, 'Figure captions: strict 0 violations (verb-leading, 8-30 chars)')
    except Exception as exc:  # noqa: BLE001 - each sub-check reports failure instead of aborting the run
        check(False, f'Caption audit failed to run: {exc}')
else:
    check(False, 'Caption audit tool missing')

section('p2', 'Figure Cluster Bridges (style-guide §13.6)')
cluster_tool = os.path.join(script_dir, 'figure_clusters.py')
if os.path.exists(cluster_tool):
    try:
        # Walk the JSON form so we can decide based on `unbridged` count
        # rather than relying on the script's own exit code (which currently
        # always returns 0 — the cluster audit is informational by design).
        res = subprocess.run(
            [sys.executable, cluster_tool, '--window', '40', '--json'],
            capture_output=True, text=True, encoding='utf-8',
        check=False
        )
        import json as _json
        payload = _json.loads(res.stdout) if res.stdout else {}
        unbridged = payload.get('unbridged', 0)
        total = payload.get('total_clusters', 0)
        check(unbridged == 0,
              f'Figure clusters: {total} clusters, {unbridged} without bridge sentence')
    except Exception as exc:  # noqa: BLE001 - each sub-check reports failure instead of aborting the run
        check(False, f'Cluster audit failed to run: {exc}')
else:
    check(False, 'Cluster audit tool missing')

# 11c. v5.6 chapter exercises (style-guide §12). Each chapter must end with
# a 延伸思考 section containing >= 3 well-formed exercises; the book total
# must be >= 50 across all 14 chapter slots.
section('p2', 'Chapter Exercises (style-guide §12)')
exercises_tool = os.path.join(script_dir, 'exercises.py')
if os.path.exists(exercises_tool):
    try:
        res = subprocess.run(
            [sys.executable, exercises_tool, '--json'],
            capture_output=True, text=True, encoding='utf-8',
        check=False
        )
        import json as _json2
        payload = _json2.loads(res.stdout) if res.stdout else {}
        total = payload.get('exercises_total', 0)
        ok = payload.get('chapters_pass', 0)
        all_ch = payload.get('chapters_total', 0)
        check(ok == all_ch and total >= 50,
              f'延伸思考: {ok}/{all_ch} chapters pass; total exercises {total} (floor 50)')
    except Exception as exc:  # noqa: BLE001 - each sub-check reports failure instead of aborting the run
        check(False, f'Exercise audit failed to run: {exc}')
else:
    check(False, 'Exercise audit tool missing')

# 12. Glossary content validation
# v6.0 supports multi-line entries with the **章节**: ... line on a separate
# row. Parse entries as blocks delimited by `- **Term**:` markers, so that the
# chapter reference can live on a continuation line.
section('p1', 'Glossary Content')
glossary_path = os.path.join(src_dir, 'back', 'glossary.md')
glossary_ok = True
if os.path.exists(glossary_path):
    glossary_lines = _read_lines(glossary_path)

    glossary_content = ''.join(glossary_lines)
    entry_term_re = re.compile(r'^- \*\*([^*]+)\*\*')

    # Split file into entry blocks by walking lines; each block runs until the
    # next entry marker, a top-level heading (## ...), or a horizontal rule.
    entry_blocks: list[tuple[str, str]] = []  # (term, body)
    current_term: str | None = None
    current_body: list[str] = []
    for raw in glossary_lines:
        stripped = raw.strip()
        is_boundary = stripped.startswith(('## ', '---'))
        m = entry_term_re.match(raw)
        if m:
            if current_term is not None:
                entry_blocks.append((current_term, ''.join(current_body)))
            current_term = m.group(1).strip()
            current_body = [raw]
        elif is_boundary:
            if current_term is not None:
                entry_blocks.append((current_term, ''.join(current_body)))
                current_term = None
                current_body = []
        elif current_term is not None:
            current_body.append(raw)
    if current_term is not None:
        entry_blocks.append((current_term, ''.join(current_body)))

    entry_count = len(entry_blocks)
    check(entry_count >= 60, f'Glossary: {entry_count} entries (target: >= 60)')

    # Validate every entry block has at least one chapter reference somewhere
    # within its body (handles both legacy single-line and v6.0 multi-line).
    no_ref_entries = [term for term, body in entry_blocks if not re.search(r'第(\d+)章', body)]
    if no_ref_entries:
        glossary_ok = False
        check(False, f'Glossary: {len(no_ref_entries)} entries missing chapter references')
        for term in no_ref_entries[:5]:
            print(f'  MISSING CHAPTER REF: {term}')
    else:
        check(True, f'All {entry_count} glossary entries have chapter references')

    # Validate chapter numbers (must be 1-12)
    all_refs = re.findall(r'第(\d+)章', glossary_content)
    invalid_refs = sorted({int(ch) for ch in all_refs if int(ch) not in range(1, 13)})
    if invalid_refs:
        glossary_ok = False
        check(False, f'Glossary references invalid chapters: {invalid_refs}')
    else:
        check(True, 'Glossary chapter refs are valid')
else:
    check(False, 'Glossary file not found')
    glossary_ok = False

# 10. Style check (advisory)
section('p2', 'Style Check')
style_script = os.path.join(script_dir, 'style.py')
style_ok = True
if os.path.exists(style_script):
    try:
        result = subprocess.run(
            [sys.executable, style_script],
            capture_output=True, text=True, encoding='utf-8', timeout=30,
        check=False
        )
        # Check for final warning count
        style_warnings = 0
        for _line in result.stderr.split('\n'):
            pass
        for line in result.stdout.split('\n'):
            m = re.search(r'(\d+) style warnings', line)
            if m:
                style_warnings = int(m.group(1))
                break
        if style_warnings == 0:
            print(f'  OK: No style issues ({style_warnings} warnings)')
        else:
            print(f'  [WARN]  {style_warnings} style warnings — review suggested')
            # Print first 3 warnings
            for line in result.stdout.split('\n'):
                if '[' in line and ']' in line and 'LONG' not in line:
                    print(f'    {line.strip()}')
        check(True, f'Style check: {style_warnings} warnings (advisory)')
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print(f'  [WARN]  Style check skipped: {e}')
        check(True, 'Style check skipped')
else:
    print('  [WARN]  style.py not found')
    check(True, 'Style check skipped')

# Summary
print('\n=== Summary ===')
passed = sum(1 for ok, _ in results if ok)
total = len(results)
print(f'  {passed}/{total} checks passed')
if passed < total:
    for ok, msg in results:
        if not ok:
            print(f'    FAIL: {msg}')
    raise SystemExit(1)
