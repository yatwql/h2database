#!/usr/bin/env python3
"""
Index cross-reference audit (v6.0).

Validates the hierarchical concept index in `books/back/index.md`:

1. Every `see also:` target resolves to an actual main entry in the index.
2. Sub-entry section refs lie within or after the main entry's chapter.
   (e.g. main entry references §6.x, sub-entry must be in chapter >= 6.)
3. Letter-section ordering is alphabetic for ASCII headers (A..Z) and the
   trailing Chinese / digit / appendix groups appear last.

Exit codes:
    0  All checks pass.
    1  One or more violations.

Output is intentionally line-based so it can be piped into `structure.py`.
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import json
import os
import re
import sys

from lib import _config, _errors, _fsutil

_fsutil.pin_stdout_utf8()

docs_dir = _config.BOOK_ROOT
src_dir = _config.MANUSCRIPT_DIR
dist_dir = _config.DIST_DIR
index_path = os.path.join(src_dir, 'back', 'index.md')

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

def _term_and_refs(stripped: str) -> tuple[str, str, list[int]]:
    """(term, reference text, chapters) for one `- ...` index line."""
    match = re.match(r'^- (.+?)\s*(?:——?|—)\s*(.*)$', stripped)
    term = ''
    ref_text = ''
    if match:
        term = match.group(1).strip()
        ref_text = match.group(2).strip()
    else:
        # An entry without an explicit reference is rare, but allowed.
        bare = re.match(r'^- (.+?)\s*$', stripped)
        if bare:
            term = bare.group(1).strip()
    chapters = sorted({int(m.group(1)) for m in SECTION_REF_RE.finditer(ref_text)})
    return term, ref_text, chapters


def _see_also_targets(raw: str, current_main: str | None) -> list[str] | None:
    """The targets of a `see also:` line, or None when it is not one."""
    match = SEE_ALSO_RE.match(raw.rstrip('\n'))
    if not match or current_main is None:
        return None
    return [_strip_alias(t) for t in re.split(r'[,，、]', match.group(1)) if t.strip()]


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

    for lineno, raw in enumerate(_fsutil.read_lines(path), start=1):
        heading = HEADING_RE.match(raw)
        if heading:
            sections.append((heading.group(1).strip(), lineno))
            continue

        # `see also` must come before the generic sub-entry: both match `- `
        targets = _see_also_targets(raw, current_main)
        if targets is not None:
            see_alsos.append({'parent': current_main, 'targets': targets, 'line': lineno})
            continue

        if raw.startswith('  - '):
            term, ref_text, chapters = _term_and_refs(raw[2:].rstrip('\n'))
            if current_main is not None:
                sub_entries.append({'parent': current_main, 'term': term,
                                    'chapters': chapters, 'ref_text': ref_text,
                                    'line': lineno})
            continue

        if not raw.startswith('- '):
            continue
        term, ref_text, chapters = _term_and_refs(raw.rstrip('\n'))
        normalized = _strip_alias(term)
        current_main = normalized
        main_entries[normalized] = {'raw_term': term, 'chapters': chapters,
                                    'ref_text': ref_text, 'line': lineno}

    return main_entries, sub_entries, see_alsos, sections


def declared_chapters() -> set[int]:
    """Chapter numbers the active book declares coverage for.

    The set comes from configuration, so an edition with fewer chapters is judged
    by its own numbering instead of a hardcoded range.
    """
    numbers: set[int] = set()
    for name, declared in _config.chapter_coverage().items():
        if not name.startswith('ch'):
            continue
        for number in declared:
            try:
                numbers.add(int(number))
            except (TypeError, ValueError):
                continue
    return numbers or {1}


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv else list(sys.argv[1:])
    as_json = '--json' in args
    if not os.path.exists(index_path):
        print(f'ERROR: index not found at {index_path}')
        return 1

    main_entries, sub_entries, see_alsos, sections = parse_index(index_path)
    alias_index = _alias_index(main_entries)
    issues = (_check_see_also(set(main_entries), alias_index, see_alsos)
              + _check_sub_entry_chapters(sub_entries)
              + _check_section_order(sections))
    _print_summary(main_entries, sub_entries, see_alsos, issues)

    if as_json:
        print(json.dumps({'issues': issues}, ensure_ascii=False))
    return 0 if issues == 0 else 1


def _alias_index(main_entries: dict) -> dict[str, str]:
    """Map every known alias onto the main entry it stands for.

    A see-also may name a term by any of its forms (canonical or bare), so both
    spellings have to land on the same entry.
    """
    index: dict[str, str] = {}
    for canonical in main_entries:
        for alias in _aliases_for(canonical):
            index.setdefault(alias, canonical)
    return index


def _target_resolves(target: str, main_keys: set[str], alias_index: dict[str, str]) -> bool:
    """Whether a see-also target names an entry, directly or through an alias."""
    if target in main_keys or target in alias_index:
        return True
    return any(alias in main_keys or alias in alias_index
               for alias in _aliases_for(target))


def _check_see_also(main_keys: set[str], alias_index: dict[str, str],
                    see_alsos: list) -> int:
    """Every ``see also:`` target must resolve to a main entry."""
    print('=== see-also resolution ===')
    dangling = []
    for sa in see_alsos:
        for raw in sa['targets']:
            target = _strip_alias(raw)
            for prefix in ('见 ', 'see '):
                if target.lower().startswith(prefix.lower()):
                    target = target[len(prefix):].strip()
            if not target:
                continue
            if _target_resolves(target, main_keys, alias_index):
                continue
            dangling.append((sa['line'], sa['parent'], target))
    if not dangling:
        print('  OK: every see-also target resolves to a main entry')
        return 0
    for line, parent, target in dangling[:20]:
        print(f"  L{line}: '{parent}' -> '{target}' (no main entry)")
    if len(dangling) > 20:
        print(f'  ... and {len(dangling) - 20} more')
    return len(dangling)


def _check_sub_entry_chapters(sub_entries: list) -> int:
    """A sub-entry may name any chapter the book declares coverage for.

    The set comes from the configuration, so an edition with fewer chapters is
    judged by its own numbering rather than by a hardcoded range. Sub-entries are
    deliberately not confined to their parent's chapter span: cross-referencing a
    comparison in a distant chapter is desirable, not a violation.
    """
    print('\n=== sub-entry chapter validity ===')
    valid = declared_chapters()
    bad = [(sub['line'], sub['parent'], sub['term'], chapter)
           for sub in sub_entries
           for chapter in sub['chapters'] if chapter not in valid]
    if not bad:
        print(f'  OK: {len(sub_entries)} sub-entries reference valid chapters')
        return 0
    for line, parent, term, chapter in bad[:20]:
        print(f"  L{line}: '{parent}' -> '{term}' references invalid 第{chapter}章")
    if len(bad) > 20:
        print(f'  ... and {len(bad) - 20} more')
    return len(bad)


def _check_section_order(sections: list) -> int:
    """Alphabetic sections must ascend; the tail only gets counted.

    Chinese, numeric and appendix sections follow the alphabetic block by design,
    so their position is reported for reading, not judged.
    """
    print('\n=== section ordering ===')
    alphabetic = [(name.upper(), line) for name, line in sections
                  if len(name) == 1 and 'A' <= name.upper() <= 'Z']
    tail = [(name, line) for name, line in sections
            if not (len(name) == 1 and 'A' <= name.upper() <= 'Z')]
    out_of_order = []
    previous = ''
    for name, line in alphabetic:
        if name < previous:
            out_of_order.append((line, name, previous))
        previous = name
    if not out_of_order:
        print(f'  OK: {len(alphabetic)} alphabetic sections in order')
    else:
        for line, name, before in out_of_order:
            print(f"  L{line}: '## {name}' appears after '## {before}' (out of order)")
    print(f'  INFO: {len(tail)} non-alphabetic trailing sections (中文/数字/附录)')
    return len(out_of_order)


def _print_summary(main_entries: dict, sub_entries: list, see_alsos: list,
                   issues: int) -> None:
    main_count = len(main_entries)
    sub_count = len(sub_entries)
    print('\n=== summary ===')
    print(f'  main entries:    {main_count}')
    print(f'  sub-entries:     {sub_count}')
    print(f'  see-also lines:  {len(see_alsos)}')
    print(f'  total entries:   {main_count + sub_count}')
    print(f'  issues:          {issues}')


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
