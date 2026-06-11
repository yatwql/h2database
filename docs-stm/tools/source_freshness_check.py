#!/usr/bin/env python3
"""Source freshness check — detect stale ClassName.java:lineno references in documentation.

Scans all docs-stm/ch*.md files for source file references, resolves them against
h2/src/main/, and reports:
  - MISSING: referenced class file does not exist in the H2 source tree
  - OFFSET:  class file exists but referenced line number exceeds current file length
  - OK:      reference is valid
  - AMBIGUOUS: class name appears in multiple source packages
"""

import re
import os
import sys
from collections import defaultdict
from datetime import date
from typing import NamedTuple, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
DOCS_DIR = os.path.join(REPO_ROOT, 'docs-stm')
H2_SRC_DIR = os.path.join(REPO_ROOT, 'h2', 'src', 'main')
POM_FILE = os.path.join(REPO_ROOT, 'h2', 'pom.xml')

CHAPTER_FILES = [
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

# Pattern: ClassName.java:lineno (also captures start of range ClassName.java:start-end)
REF_RE = re.compile(r'\b(\w+)\.java:(\d+)')

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
class Reference(NamedTuple):
    """A single ClassName.java:lineno reference found in documentation."""
    doc_file: str       # e.g. 'ch3-packages.md'
    doc_line: int       # 1-based line number in the doc file
    class_name: str     # e.g. 'MVStore'
    lineno: int         # referenced line number


class Resolution(NamedTuple):
    """Resolution status for a single Reference."""
    ref: Reference
    status: str          # 'MISSING' | 'FOUND' | 'AMBIGUOUS'
    paths: list          # list of absolute file paths


class Verification(NamedTuple):
    """Line-number verification result for a resolved Reference."""
    ref: Reference
    status: str          # 'OK' | 'OFFSET' | 'MISSING' | 'ERROR'
    file_path: Optional[str]
    detail: str          # extra description for OFFSET/ERROR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_h2_version() -> str:
    """Extract H2 version from pom.xml."""
    try:
        with open(POM_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.search(r'<version>(.+?)</version>', line)
                if m:
                    return m.group(1).strip()
    except IOError:
        pass
    return 'unknown'


def build_class_index() -> dict:
    """Return {ClassName: [list of absolute .java file paths]} from h2/src/main/."""
    index: dict = defaultdict(list)
    if not os.path.isdir(H2_SRC_DIR):
        return index
    for root, _dirs, files in os.walk(H2_SRC_DIR):
        for f in files:
            if f.endswith('.java'):
                name = f[:-5]          # strip '.java'
                index[name].append(os.path.join(root, f))
    return index


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract_references() -> list:
    """Parse all chapter files for ClassName.java:lineno refs outside code fences."""
    refs: list = []
    for ch_name in CHAPTER_FILES:
        ch_path = os.path.join(DOCS_DIR, ch_name)
        if not os.path.exists(ch_path):
            print(f'  [WARN] Chapter file not found: {ch_name}', file=sys.stderr)
            continue
        with open(ch_path, 'r', encoding='utf-8') as fh:
            lines = fh.readlines()

        in_fence = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Toggle fence on backtick-fence lines
            if stripped.startswith('```'):
                in_fence = not in_fence
                continue

            # Skip content inside fences
            if in_fence:
                continue

            # Extract all references on this line
            for m in REF_RE.finditer(line):
                refs.append(Reference(
                    doc_file=ch_name,
                    doc_line=i,
                    class_name=m.group(1),
                    lineno=int(m.group(2)),
                ))
    return refs


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
def resolve_references(refs: list, class_index: dict) -> list:
    """Map each Reference to file path(s) using the class index."""
    resolved: list = []
    for r in refs:
        if r.class_name not in class_index:
            resolved.append(Resolution(r, 'MISSING', []))
        elif len(class_index[r.class_name]) == 1:
            resolved.append(Resolution(r, 'FOUND', class_index[r.class_name]))
        else:
            resolved.append(Resolution(r, 'AMBIGUOUS', class_index[r.class_name]))
    return resolved


# ---------------------------------------------------------------------------
# Line-number verification
# ---------------------------------------------------------------------------
def verify_line_numbers(resolved: list) -> list:
    """Check each resolved reference's line number against the source file."""
    results: list = []
    for res in resolved:
        r = res.ref
        if res.status == 'MISSING':
            results.append(Verification(r, 'MISSING', None, ''))
            continue

        file_path = res.paths[0]   # first path if ambiguous
        try:
            with open(file_path, 'r', encoding='utf-8') as fh:
                file_lines = fh.readlines()
            total = len(file_lines)
            if r.lineno > total:
                offset = total - r.lineno
                detail = f'file has {total} lines, offset {offset}'
                results.append(Verification(r, 'OFFSET', file_path, detail))
            else:
                results.append(Verification(r, 'OK', file_path, ''))
        except IOError as e:
            results.append(Verification(r, 'ERROR', file_path, str(e)))
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def format_rel_path(path: str) -> str:
    """Convert an absolute file path to org/h2/... relative form."""
    rel = os.path.relpath(path, H2_SRC_DIR).replace('\\', '/')
    if rel.startswith('org/h2/'):
        return rel
    return f'org/h2/{rel}'


def print_report(results: list, class_index: dict) -> None:
    """Print the formatted freshness report."""
    h2_version = get_h2_version()
    today = date.today().isoformat()

    # Categorise
    ok = [r for r in results if r.status == 'OK']
    offset = [r for r in results if r.status == 'OFFSET']
    missing = [r for r in results if r.status == 'MISSING']
    errors = [r for r in results if r.status == 'ERROR']

    total = len(results)
    valid = len(ok)
    issues = total - valid

    # -- Header --
    print('====== Source Freshness Report ======')
    print(f'Generated: {today}')
    print(f'Source base: v{h2_version}')
    print()

    # -- MISSING --
    if missing:
        print('MISSING references (file not found):')
        for v in missing:
            print(f'  {v.ref.doc_file}:{v.ref.doc_line}'
                  f' -- {v.ref.class_name}.java:{v.ref.lineno}')
        print()

    # -- OFFSET --
    if offset:
        print('OFFSET references (line beyond file end):')
        for v in offset:
            rel_path = format_rel_path(v.file_path) if v.file_path else ''
            print(f'  {v.ref.doc_file}:{v.ref.doc_line}'
                  f' -- {v.ref.class_name}.java:{v.ref.lineno}'
                  f' ({v.detail})')
        print()

    # -- AMBIGUOUS (advisory) --
    ambiguous_names = {r.ref.class_name for r in results
                       if r.ref.class_name in class_index
                       and len(class_index[r.ref.class_name]) > 1}
    if ambiguous_names:
        print('AMBIGUOUS class names (advisory -- first file used for check):')
        for name in sorted(ambiguous_names):
            paths = class_index[name]
            print(f'  {name}.java -> {len(paths)} locations:')
            for p in paths:
                print(f'    {format_rel_path(p)}')
        print()

    # -- ERRORS --
    if errors:
        print('ERROR references (file read error):')
        for v in errors:
            print(f'  {v.ref.doc_file}:{v.ref.doc_line}'
                  f' -- {v.ref.class_name}.java:{v.ref.lineno}'
                  f' ({v.detail})')
        print()

    # -- Counts --
    print(f'OK references: {len(ok)}')
    print(f'OFFSET references: {len(offset)}')
    print(f'MISSING references: {len(missing)}')
    if errors:
        print(f'ERROR references: {len(errors)}')
    print()

    # -- Summary --
    print('====== Summary ======')
    print(f'Total references: {total}')
    if total > 0:
        pct_valid = (valid / total) * 100
        pct_issues = (issues / total) * 100
        print(f'Valid: {valid} ({pct_valid:.1f}%)')
        print(f'Issues: {issues} ({pct_issues:.1f}%)')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    try:
        print('Building class index from H2 source (h2/src/main/)...')
        class_index = build_class_index()
        if not class_index:
            print(f'ERROR: H2 source directory not found at {H2_SRC_DIR}', file=sys.stderr)
            sys.exit(1)
        print(f'Indexed {len(class_index)} unique class names')
        print()

        print('Extracting references from chapter files...')
        refs = extract_references()
        print(f'Found {len(refs)} references (outside code fences)')
        print()

        print('Resolving references to source files...')
        resolved = resolve_references(refs, class_index)
        print(f'Resolved: {sum(1 for r in resolved if r.status == "FOUND")} found, '
              f'{sum(1 for r in resolved if r.status == "AMBIGUOUS")} ambiguous, '
              f'{sum(1 for r in resolved if r.status == "MISSING")} missing')
        print()

        print('Verifying line numbers...')
        results = verify_line_numbers(resolved)

        print()
        print()
        print_report(results, class_index)

    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
