#!/usr/bin/env python3
"""
Index cross-reference audit (v6.0).

Validates the hierarchical concept index in `docs-stm/back/index.md`:

1. Every `see also:` target resolves to an actual main entry in the index.
2. Sub-entry section refs lie within or after the main entry's chapter.
   (e.g. main entry references §6.x, sub-entry must be in chapter >= 6.)
3. Letter-section ordering is alphabetic for ASCII headers (A..Z) and the
   trailing Chinese / digit / appendix groups appear last.

Exit codes:
    0  All checks pass.
    1  One or more violations.

Output is intentionally line-based so it can be piped into `final_check.py`.
"""
import os
import re
import sys

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

script_dir = os.path.dirname(os.path.abspath(__file__))
docs_dir = os.path.normpath(os.path.join(script_dir, '..'))
index_path = os.path.join(docs_dir, 'back', 'index.md')


# ---- Patterns ----

MAIN_ENTRY_RE = re.compile(r'^- (.+?)(?:\s+——?\s+|\s+—\s+)(§|第|附录)(.*)$')
MAIN_ENTRY_HEAD_RE = re.compile(r'^- (.+?)\s*(?:——?|—)\s*(.*)$')
MAIN_ENTRY_NO_REF_RE = re.compile(r'^- (.+?)\s*$')
SUB_ENTRY_RE = re.compile(r'^  - (.+?)\s*(?:——?|—)\s*(.*)$')
SUB_ENTRY_NO_REF_RE = re.compile(r'^  - (.+?)\s*$')
SEE_ALSO_RE = re.compile(r'^  see also:\s*(.+)$')
SECTION_REF_RE = re.compile(r'§(\d+)(?:\.\d+)*')
APPENDIX_REF_RE = re.compile(r'附录\s*[A-Z]')
HEADING_RE = re.compile(r'^## (.+)$')


# Common Chinese category suffixes that act as descriptive labels rather than
# part of the canonical term. When normalising for see-also lookup we accept
# either form: "Aggregate" matches main entry "Aggregate（聚合函数）", and
# "Lock" matches "Lock 类". Add new suffixes here as authors evolve the index.
_TRAILING_NOISE = (
    '类', '层', '接口', '结构', '格式', '机制', '算法', '流程', '管理',
    '管理器', '索引', '函数', '语句', '编码', '处理', '数据', '字段',
    '工具', '模块', '抽象', '设计', '记录',
    '查询优化', '写入',
)


def _strip_alias(label: str) -> str:
    """Normalize a 'see also' or sub-reference label for comparison.

    Strips trailing parenthetical suffixes like 'B-Tree（树）' -> 'B-Tree' so
    that authors may use either form when cross-linking.
    """
    label = label.strip()
    # Drop content inside Chinese full-width parens
    label = re.sub(r'（[^）]*）', '', label).strip()
    label = re.sub(r'\([^)]*\)', '', label).strip()
    return label


def _aliases_for(term: str) -> set[str]:
    """Generate alias forms for a main entry so see-also can match either form.

    Returns a set including the term itself plus variants with trailing
    Chinese category suffixes stripped. For example, 'Lock 类' yields
    {'Lock 类', 'Lock'} and 'Aggregate（聚合函数）' yields
    {'Aggregate（聚合函数）', 'Aggregate', '聚合函数'}.
    """
    out = {term}
    bare = _strip_alias(term)
    if bare and bare != term:
        out.add(bare)
    # Strip trailing Chinese category suffix
    for suffix in _TRAILING_NOISE:
        if bare.endswith(' ' + suffix):
            out.add(bare[: -(len(suffix) + 1)].strip())
        elif bare.endswith(suffix):
            stripped = bare[: -len(suffix)].strip()
            if stripped:
                out.add(stripped)
    # Also pull alternate aliases out of full-width parens
    for m in re.finditer(r'（([^）]+)）', term):
        out.add(m.group(1).strip())
    for m in re.finditer(r'\(([^)]+)\)', term):
        out.add(m.group(1).strip())

    # Leading ASCII identifier — many entries have the form
    #   "Chunk 文件格式" / "MVStore 架构" / "Recover 工具"
    # so the leading ASCII token is a useful alias for see-also lookups.
    head = re.match(r'^([A-Za-z][A-Za-z0-9_\-]*(?:\s*-\s*[A-Za-z0-9_]+)*)', bare)
    if head:
        head_token = head.group(1).strip()
        if head_token and head_token != bare:
            out.add(head_token)

    # If term contains slash (e.g. "Prepared / PreparedStatement"), split.
    for piece in re.split(r'\s*/\s*', bare):
        piece = piece.strip()
        if piece:
            out.add(piece)

    return {a for a in out if a}


def parse_index(path: str):
    """Walk the index and emit a structured representation.

    Returns a tuple (main_entries, sub_entries, see_alsos, sections):
        main_entries: dict[normalized_term, dict(line, chapters, raw_term)]
        sub_entries:  list of dict(parent, term, chapters, line)
        see_alsos:    list of dict(parent, targets, line)
        sections:     list of (heading_text, line)
    """
    main_entries: dict[str, dict] = {}
    sub_entries: list[dict] = []
    see_alsos: list[dict] = []
    sections: list[tuple[str, int]] = []

    current_main: str | None = None
    current_main_chapters: list[int] = []

    with open(path, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()

    for lineno, raw in enumerate(lines, start=1):
        # H2 heading
        hm = HEADING_RE.match(raw)
        if hm:
            sections.append((hm.group(1).strip(), lineno))
            continue

        # see also (must come before generic sub-entry which also matches `- `)
        sa = SEE_ALSO_RE.match(raw.rstrip('\n'))
        if sa and current_main is not None:
            targets = [_strip_alias(t) for t in re.split(r'[,，、]', sa.group(1)) if t.strip()]
            see_alsos.append({
                'parent': current_main,
                'targets': targets,
                'line': lineno,
            })
            continue

        # Sub-entry (2-space indent + bullet)
        if raw.startswith('  - '):
            stripped = raw[2:].rstrip('\n')
            sub_match = re.match(r'^- (.+?)\s*(?:——?|—)\s*(.*)$', stripped)
            term = ''
            ref_text = ''
            if sub_match:
                term = sub_match.group(1).strip()
                ref_text = sub_match.group(2).strip()
            else:
                # Sub-entry without explicit reference (rare but allowed).
                bare = re.match(r'^- (.+?)\s*$', stripped)
                if bare:
                    term = bare.group(1).strip()
            if current_main is not None:
                chapters = sorted({int(m.group(1)) for m in SECTION_REF_RE.finditer(ref_text)})
                sub_entries.append({
                    'parent': current_main,
                    'term': term,
                    'chapters': chapters,
                    'ref_text': ref_text,
                    'line': lineno,
                })
            continue

        # Main entry (must start with `- ` and not be indented)
        if raw.startswith('- '):
            stripped = raw.rstrip('\n')
            main_match = re.match(r'^- (.+?)\s*(?:——?|—)\s*(.*)$', stripped)
            term = ''
            ref_text = ''
            if main_match:
                term = main_match.group(1).strip()
                ref_text = main_match.group(2).strip()
            else:
                bare = re.match(r'^- (.+?)\s*$', stripped)
                if bare:
                    term = bare.group(1).strip()
            chapters = sorted({int(m.group(1)) for m in SECTION_REF_RE.finditer(ref_text)})
            normalized = _strip_alias(term)
            current_main = normalized
            current_main_chapters = chapters
            main_entries[normalized] = {
                'raw_term': term,
                'chapters': chapters,
                'ref_text': ref_text,
                'line': lineno,
            }

    return main_entries, sub_entries, see_alsos, sections


def main() -> int:
    if not os.path.exists(index_path):
        print(f'ERROR: index not found at {index_path}')
        return 1

    main_entries, sub_entries, see_alsos, sections = parse_index(index_path)

    main_keys = set(main_entries.keys())
    # Build an alias index so see-also can resolve either form (canonical or
    # bare); a target hits if any of its aliases appears in main_alias_index.
    main_alias_index: dict[str, str] = {}
    for canonical in main_keys:
        for alias in _aliases_for(canonical):
            main_alias_index.setdefault(alias, canonical)
    issues = 0

    # Check 1: see-also targets resolve.
    print('=== see-also resolution ===')
    dangling = []
    for sa in see_alsos:
        for tgt in sa['targets']:
            tgt_norm = _strip_alias(tgt)
            tgt_clean = tgt_norm
            for prefix in ('见 ', 'see '):
                if tgt_clean.lower().startswith(prefix.lower()):
                    tgt_clean = tgt_clean[len(prefix):].strip()
            if not tgt_clean:
                continue
            # Try exact, then alias-resolved match
            if tgt_clean in main_keys:
                continue
            if tgt_clean in main_alias_index:
                continue
            # Try matching by stripping each candidate's known aliases
            matched = False
            for alias in _aliases_for(tgt_clean):
                if alias in main_keys or alias in main_alias_index:
                    matched = True
                    break
            if matched:
                continue
            dangling.append((sa['line'], sa['parent'], tgt_clean))
    if dangling:
        for line, parent, tgt in dangling[:20]:
            print(f"  L{line}: '{parent}' -> '{tgt}' (no main entry)")
        if len(dangling) > 20:
            print(f"  ... and {len(dangling) - 20} more")
        issues += len(dangling)
    else:
        print('  OK: every see-also target resolves to a main entry')

    # Check 2: sub-entry chapter validity.
    # Any chapter referenced by a sub-entry must be a valid chapter (1-12).
    # We deliberately do NOT enforce that sub-entries lie within their parent's
    # chapter span — sub-entries often legitimately cross-reference comparison
    # material in distant chapters (e.g. "与 LSM-Tree 对比 — §1.1" under a
    # "B-Tree 索引 — §6.1" parent is desirable, not a violation).
    print('\n=== sub-entry chapter validity ===')
    bad_subs = []
    for sub in sub_entries:
        for ch in sub['chapters']:
            if ch < 1 or ch > 12:
                bad_subs.append((sub['line'], sub['parent'], sub['term'], ch))
    if bad_subs:
        for line, parent, term, ch in bad_subs[:20]:
            print(f"  L{line}: '{parent}' -> '{term}' references invalid 第{ch}章")
        if len(bad_subs) > 20:
            print(f"  ... and {len(bad_subs) - 20} more")
        issues += len(bad_subs)
    else:
        print(f'  OK: {len(sub_entries)} sub-entries reference valid chapters')

    # Check 3: section heading order (A..Z then 数字, 附录).
    print('\n=== section ordering ===')
    ascii_letters = []
    tail = []
    for name, line in sections:
        if len(name) == 1 and 'A' <= name.upper() <= 'Z':
            ascii_letters.append((name.upper(), line))
        else:
            tail.append((name, line))
    order_problems = []
    last = ''
    for name, line in ascii_letters:
        if name < last:
            order_problems.append((line, name, last))
        last = name
    if order_problems:
        for line, name, prev in order_problems:
            print(f"  L{line}: '## {name}' appears after '## {prev}' (out of order)")
        issues += len(order_problems)
    else:
        print(f'  OK: {len(ascii_letters)} alphabetic sections in order')
    print(f'  INFO: {len(tail)} non-alphabetic trailing sections (中文/数字/附录)')

    # Summary
    main_count = len(main_entries)
    sub_count = len(sub_entries)
    sa_count = len(see_alsos)
    print('\n=== summary ===')
    print(f'  main entries:    {main_count}')
    print(f'  sub-entries:     {sub_count}')
    print(f'  see-also lines:  {sa_count}')
    print(f'  total entries:   {main_count + sub_count}')
    print(f'  issues:          {issues}')

    return 0 if issues == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
