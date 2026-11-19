#!/usr/bin/env python3
"""Source freshness check — detect stale ClassName.java:lineno references in documentation.

Scans all books/ch*.md files for source file references, resolves them against
h2/src/main/, and reports:
  - MISSING: referenced class file does not exist in the H2 source tree
  - OFFSET:  class file exists but referenced line number exceeds current file length
  - OK:      reference is valid
  - AMBIGUOUS: class name appears in multiple source packages
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import difflib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from typing import NamedTuple

from lib import _config, _fsutil

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
DOCS_DIR = _config.MANUSCRIPT_DIR
SUFFIXES = _config.source_suffixes()
PACKAGE_PREFIX = _config.SOURCES.get('package_prefix') or 'unknown'
SOURCE_DIR = _config.source_tree('src_main')
POM_PATH = _config.source_tree('pom_root')
# Known (accepted) symbol drift, so an upstream rename does not break the gate
# on every run. Refresh with: python source_refs.py --update-baseline
BASELINE_PATH = _config.baseline_path('source_symbol')

CHAPTER_FILES = [
    'ch1-2-architecture.md',
    'ch3-packages.md',
    'ch4-5-modules-processes.md',
    'ch6-1-data-structures.md',
    'ch6-2-storage-algorithms.md',
    'ch6-3-query-algorithms.md',
    'ch7-sql-execution.md',
    'ch8-query-optimizer.md',
    'ch9-10-persistence-locking.md',
    'ch11-12-guide-summary.md',
]

# Pattern: ClassName.java:lineno (also captures start of range ClassName.java:start-end)
REF_RE = re.compile(r'\b(\w+)(?:' + '|'.join(re.escape(x) for x in SUFFIXES) + r'):(\d+)')

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
    file_path: str | None
    detail: str          # extra description for OFFSET/ERROR

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def get_h2_version() -> str:
    """Project version from the configured build file (empty when absent)."""
    try:
        lines = _fsutil.read_lines(POM_PATH)
    except (SystemExit, OSError):
        return 'unknown'
    for line in lines:
        m = re.search(r'<version>(.+?)</version>', line)
        if m:
            return m.group(1).strip()
    return 'unknown'

def build_class_index() -> dict:
    """Return {ClassName: [list of absolute .java file paths]} from h2/src/main/."""
    index: dict = defaultdict(list)
    if not os.path.isdir(SOURCE_DIR):
        return index
    for root, _dirs, files in os.walk(SOURCE_DIR):
        for f in files:
            if f.endswith(tuple(SUFFIXES)):
                name = os.path.splitext(f)[0]
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
        lines = _fsutil.read_lines(ch_path)

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

# Pattern: ClassName.method( — a symbol-level claim about the source tree.
SYMBOL_RE = re.compile(r'\b([A-Z]\w{2,})\.(\w{2,})\s*\(')

class SymbolClaim(NamedTuple):
    """A ``Class.method(`` reference found in documentation."""
    doc_file: str
    doc_line: int
    class_name: str
    method: str

# ---------------------------------------------------------------------------
# Symbol-level claims
# ---------------------------------------------------------------------------
def extract_symbol_claims() -> list:
    """Collect ClassName.method( claims from chapter prose (outside fences)."""
    claims: list = []
    for ch_name in CHAPTER_FILES:
        ch_path = os.path.join(DOCS_DIR, ch_name)
        if not os.path.exists(ch_path):
            continue
        lines = _fsutil.read_lines(ch_path)
        in_fence = False
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('```'):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for m in SYMBOL_RE.finditer(line):
                claims.append(SymbolClaim(ch_name, i, m.group(1), m.group(2)))
    return claims

def verify_symbol_claims(claims: list, class_index: dict) -> list:
    """Return claims whose method does not exist in the resolved class file."""
    broken: list = []
    cache: dict = {}
    for claim in claims:
        paths = class_index.get(claim.class_name)
        if not paths or len(paths) != 1:
            continue  # unknown or ambiguous class: skipped, not an error
        path = paths[0]
        if path not in cache:
            try:
                with open(path, encoding='utf-8') as fh:
                    cache[path] = fh.read()
            except OSError:
                cache[path] = ''
        body = cache[path]
        # Declaration, call or javadoc mention of the method all count.
        if body and claim.method not in body:
            broken.append((claim, format_rel_path(path)))
    return broken

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
            with open(file_path, encoding='utf-8') as fh:
                file_lines = fh.readlines()
            total = len(file_lines)
            if r.lineno > total:
                offset = total - r.lineno
                detail = f'file has {total} lines, offset {offset}'
                results.append(Verification(r, 'OFFSET', file_path, detail))
            else:
                results.append(Verification(r, 'OK', file_path, ''))
        except OSError as e:
            results.append(Verification(r, 'ERROR', file_path, str(e)))
    return results

# ---------------------------------------------------------------------------
# Drift baseline (keeps upstream renames from breaking the gate every run)
# ---------------------------------------------------------------------------
def _claim_key(doc_file: str, class_name: str, method: str) -> str:
    return f'{doc_file}::{class_name}::{method}'

def load_baseline(path: str | None = None) -> dict:
    """Return the accepted-drift baseline (empty skeleton when absent)."""
    target = path or BASELINE_PATH
    if not os.path.isfile(target):
        return {'h2_version': '', 'accepted': []}
    try:
        data = json.loads(_fsutil.read_text_raw(target))
    except (OSError, json.JSONDecodeError) as exc:
        print(f'  [WARN] cannot read baseline {target}: {exc}', file=sys.stderr)
        return {'h2_version': '', 'accepted': []}
    data.setdefault('accepted', [])
    data.setdefault('h2_version', '')
    return data

def save_baseline(broken: list, h2_version: str, path: str | None = None) -> None:
    """Record the current drift as accepted."""
    target = path or BASELINE_PATH
    payload = {
        'h2_version': h2_version,
        'note': 'Accepted symbol drift. Refresh after an upstream update.',
        'accepted': sorted(
            (_claim_key(c.doc_file, c.class_name, c.method) for c, _rel in broken)
        ),
    }
    _fsutil.ensure_dir(target)
    _fsutil.write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')

def split_drift(broken: list, baseline: dict) -> tuple[list, list]:
    """Split broken claims into (new_drift, known_drift)."""
    accepted = set(baseline.get('accepted', []))
    new, known = [], []
    for claim, rel in broken:
        (known if _claim_key(claim.doc_file, claim.class_name, claim.method) in accepted
         else new).append((claim, rel))
    return new, known

def suggest_renames(claim, class_index: dict) -> list[str]:
    """Nearest method names in the class file — a rename hint after a bump."""
    paths = class_index.get(claim.class_name) or []
    if len(paths) != 1:
        return []
    try:
        body = _fsutil.read_text_raw(paths[0])
    except OSError:
        return []
    names = set(re.findall(r'\b(\w+)\s*\(', body))
    return difflib.get_close_matches(claim.method, sorted(names), n=3, cutoff=0.5)

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def format_rel_path(path: str) -> str:
    """Convert an absolute file path to its source-root relative form."""
    return os.path.relpath(path, SOURCE_DIR).replace('\\', '/')

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
            format_rel_path(v.file_path) if v.file_path else ''
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
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-baseline', action='store_true',
                        help='record current symbol drift as accepted')
    parser.add_argument('--json', action='store_true',
                        help='machine-readable summary')
    parser.add_argument('--suggest', action='store_true',
                        help='print nearest-method rename hints for drifted claims')
    parser.add_argument('--strict-symbols', action='store_true',
                        help='treat known (baselined) drift as a failure too')
    args = parser.parse_args(argv)

    h2_version = get_h2_version()
    try:
        print('Building class index from H2 source (h2/src/main/)...')
        class_index = build_class_index()
        if not class_index:
            print(f'  [skip] H2 source tree not found at {SOURCE_DIR}; '
                  f'set [sources].src_main in data/config/config.json', file=sys.stderr)
            return 0
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

        print('Verifying Class.method claims against the source tree...')
        broken_symbols = verify_symbol_claims(extract_symbol_claims(), class_index)
        baseline = load_baseline()
        new_drift, known_drift = split_drift(broken_symbols, baseline)

        if args.update_baseline:
            save_baseline(broken_symbols, h2_version)
            print(f'  baseline updated: {len(broken_symbols)} accepted claim(s) '
                  f'-> {os.path.relpath(BASELINE_PATH, REPO_ROOT)}')
            new_drift = []
        elif broken_symbols:
            print(f'  {len(broken_symbols)} symbol claim(s) not found in source: '
                  f'{len(new_drift)} new, {len(known_drift)} known')
            for claim, rel in new_drift[:20]:
                print(f'    NEW  {claim.doc_file}:{claim.doc_line}  '
                      f'{claim.class_name}.{claim.method}(  -> {rel}')
                if args.suggest:
                    hints = suggest_renames(claim, class_index)
                    print(f'         maybe: {", ".join(hints) or "(no close match)"}')
            for claim, _rel in known_drift[:5]:
                print(f'    known {claim.doc_file}:{claim.doc_line}  '
                      f'{claim.class_name}.{claim.method}(')
            if known_drift:
                print('    (refresh baseline: --update-baseline)')
        symbol_failures = len(new_drift) + (len(known_drift) if args.strict_symbols else 0)

        if args.json:
            print(json.dumps({
                'references': len(results),
                'ok': sum(1 for r in results if r.status == 'OK'),
                'offset': sum(1 for r in results if r.status == 'OFFSET'),
                'missing': sum(1 for r in results if r.status == 'MISSING'),
                'symbol_new': len(new_drift),
                'symbol_known': len(known_drift),
            }, ensure_ascii=False, indent=2))
            return symbol_failures and 0 or (1 if symbol_failures else 0)
        print()
        print()
        print_report(results, class_index)
        if symbol_failures:
            print(f'Symbol drift: {symbol_failures} claim(s) need review '
                  f'(run with --suggest for rename hints)')
            return 1
        return 0

    except Exception as e:  # noqa: BLE001 - top-level guard must report, not abort
        print(f'ERROR: {e}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
