#!/usr/bin/env python3
"""Source freshness check — detect stale ClassName.java:lineno references in documentation.

Scans all books/ch*.md files for source file references, resolves them against
the configured source root, and reports:
  - MISSING: referenced file does not exist in the source tree
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
import functools
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from typing import NamedTuple

from lib import _config, _errors, _fsutil

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..', '..', '..'))
def suffixes() -> list[str]:
    """Source suffixes this book declares, read when asked."""
    return _config.source_suffixes()


def package_prefix() -> str:
    """The package prefix the coordinates are written in."""
    return _config.SOURCES.get('package_prefix') or 'unknown'


def source_root() -> str:
    """The source tree the references point into."""
    return _config.source_tree('src_main')


def pom_path() -> str:
    return _config.source_tree('pom_root')


def baseline_file() -> str:
    """Known (accepted) symbol drift; refresh with `--update-baseline`."""
    return _config.baseline_path('source_symbol')

# Scanned files come from book.toml, so a renamed or merged chapter can never
# leave the gate checking a file that does not exist. Appendices are
# prose too: their coordinates and `Class.method(` claims follow the same rules
# instead of waiting for a proofreading pass.
def scanned_chapter_files() -> list[str]:
    """Files the gate reads: every chapter and appendix, from book.toml."""
    return _config.chapter_names(include_cover=False)

# Pattern: ClassName.java:lineno (also captures start of range ClassName.java:start-end)
@functools.lru_cache(maxsize=4)
def ref_re(source_suffixes: tuple[str, ...]) -> re.Pattern:
    """`Class.java:12` shaped references, for the suffixes a book declares."""
    return re.compile(r'\b(\w+)(?:' + '|'.join(re.escape(x) for x in source_suffixes)
                      + r'):(\d+)')

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



def get_project_version() -> str:
    """Project version from the configured build file (empty when absent)."""
    try:
        lines = _fsutil.read_lines(pom_path())
    except (SystemExit, OSError):
        return 'unknown'
    for line in lines:
        m = re.search(r'<version>(.+?)</version>', line)
        if m:
            return m.group(1).strip()
    return 'unknown'

def _preferred_paths() -> dict:
    """Class name -> source-relative path recorded by the inventory.

    Duplicate stems (e.g. DataType in two packages) resolve to the file the
    manuscript actually cites, instead of the first match on disk.
    """
    path = _config.state_path('source-inventory.json')
    if not os.path.isfile(path):
        return {}
    try:
        payload = json.loads(_fsutil.read_text(path))
    except (OSError, ValueError):
        return {}
    preferred: dict = {}
    for package in (payload.get('packages') or {}).values():
        for unit in package.get('classes') or []:
            rel = unit.get('rel')
            if rel:
                preferred.setdefault(unit['name'], rel)
    return preferred


def build_class_index(source_dir: str | None = None) -> dict:
    """Map file stem -> absolute paths, inventory-preferred file first."""
    index: dict = defaultdict(list)
    root_dir = source_dir or source_root()
    if not os.path.isdir(root_dir):
        return index
    preferred = _preferred_paths()
    for root, _dirs, files in os.walk(root_dir):
        for f in files:
            if f.endswith(tuple(suffixes())):
                index[os.path.splitext(f)[0]].append(os.path.join(root, f))
    for name, paths in index.items():
        rel = preferred.get(name)
        if rel:
            paths.sort(key=lambda item: 0 if item.endswith(rel) else 1)
    return index

def extract_references(chapter_files: list[str] | None = None,
                       docs_dir: str | None = None) -> list:
    """Parse all chapter files for ClassName.java:lineno refs outside code fences."""
    refs: list = []
    for ch_name in (chapter_files or scanned_chapter_files()):
        ch_path = os.path.join(docs_dir or _config.MANUSCRIPT_DIR, ch_name)
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
            for m in ref_re(tuple(suffixes())).finditer(line):
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
def extract_symbol_claims(chapter_files: list[str] | None = None,
                          docs_dir: str | None = None) -> list:
    """Collect ClassName.method( claims from chapter prose (outside fences)."""
    claims: list = []
    for ch_name in (chapter_files or scanned_chapter_files()):
        ch_path = os.path.join(docs_dir or _config.MANUSCRIPT_DIR, ch_name)
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
def _count_file_lines(path: str) -> int:
    """Line count of a source file (OSError propagates to the caller)."""
    try:
        with open(path, encoding='utf-8') as fh:
            return sum(1 for _ in fh)
    except OSError as exc:
        exc.add_note(f'while reading {path}')
        raise


def verify_line_numbers(resolved: list) -> list:
    """Check each resolved reference's line number against the source file."""
    results: list = []
    for res in resolved:
        r = res.ref
        if res.status == 'MISSING':
            results.append(Verification(r, 'MISSING', None, ''))
            continue

        file_path = res.paths[0]   # inventory-preferred / first path
        if len(res.paths) > 1:
            for candidate in res.paths:
                try:
                    if _count_file_lines(candidate) >= r.lineno:
                        file_path = candidate
                        break
                except OSError:
                    continue
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
    target = path or baseline_file()
    if not os.path.isfile(target):
        return {'source_version': '', 'accepted': []}
    try:
        data = json.loads(_fsutil.read_text_raw(target))
    except (OSError, json.JSONDecodeError) as exc:
        print(f'  [WARN] cannot read baseline {target}: {exc}', file=sys.stderr)
        return {'source_version': '', 'accepted': []}
    data.setdefault('accepted', [])
    data.setdefault('source_version', data.pop('h2_version', ''))
    return data

def save_baseline(broken: list, source_version: str, path: str | None = None) -> None:
    """Record the current drift as accepted."""
    target = path or baseline_file()
    payload = {
        'updated': date.today().isoformat(),
        'source_version': source_version,
        'note': 'Accepted symbol drift. Refresh after an upstream update.',
        'accepted': sorted(
            {_claim_key(c.doc_file, c.class_name, c.method) for c, _rel in broken}
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
    return os.path.relpath(path, source_root()).replace('\\', '/')

def _print_missing(missing: list) -> None:
    if not missing:
        return
    print('MISSING references (file not found):')
    for v in missing:
        print(f'  {v.ref.doc_file}:{v.ref.doc_line}'
              f' -- {v.ref.class_name}.java:{v.ref.lineno}')
    print()


def _print_offset(offset: list) -> None:
    if not offset:
        return
    print('OFFSET references (line beyond file end):')
    for v in offset:
        print(f'  {v.ref.doc_file}:{v.ref.doc_line}'
              f' -- {v.ref.class_name}.java:{v.ref.lineno}'
              f' ({v.detail})')
    print()


def _print_ambiguous(results: list, class_index: dict) -> None:
    ambiguous_names = {r.ref.class_name for r in results
                       if r.ref.class_name in class_index
                       and len(class_index[r.ref.class_name]) > 1}
    if not ambiguous_names:
        return
    print('AMBIGUOUS class names (advisory -- first file used for check):')
    for name in sorted(ambiguous_names):
        paths = class_index[name]
        print(f'  {name}.java -> {len(paths)} locations:')
        for path in paths:
            print(f'    {format_rel_path(path)}')
    print()


def _print_errors(errors: list) -> None:
    if not errors:
        return
    print('ERROR references (file read error):')
    for v in errors:
        print(f'  {v.ref.doc_file}:{v.ref.doc_line}'
              f' -- {v.ref.class_name}.java:{v.ref.lineno}'
              f' ({v.detail})')
    print()


def _print_summary(results: list, counts: dict[str, int]) -> None:
    total = counts['total']
    valid = counts['valid']
    issues = total - valid
    print('====== Summary ======')
    print(f'Total references: {total}')
    if total > 0:
        print(f'Valid: {valid} ({(valid / total) * 100:.1f}%)')
        print(f'Issues: {issues} ({(issues / total) * 100:.1f}%)')


def print_report(results: list, class_index: dict,
                 h2_version: str | None = None) -> None:
    """Print the formatted freshness report."""
    h2_version = h2_version or get_project_version()
    today = date.today().isoformat()

    ok = [r for r in results if r.status == 'OK']
    offset = [r for r in results if r.status == 'OFFSET']
    missing = [r for r in results if r.status == 'MISSING']
    errors = [r for r in results if r.status == 'ERROR']

    print('====== Source Freshness Report ======')
    print(f'Generated: {today}')
    print(f'Source base: {h2_version}')
    print()

    _print_missing(missing)
    _print_offset(offset)
    _print_ambiguous(results, class_index)
    _print_errors(errors)

    print(f'OK references: {len(ok)}')
    print(f'OFFSET references: {len(offset)}')
    print(f'MISSING references: {len(missing)}')
    if errors:
        print(f'ERROR references: {len(errors)}')
    print()

    _print_summary(results, {'total': len(results), 'valid': len(ok)})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-baseline', action='store_true',
                        help='record current symbol drift as accepted')
    parser.add_argument('--prune', action='store_true',
                        help='drop accepted entries that now resolve')
    parser.add_argument('--json', action='store_true',
                        help='machine-readable summary')
    parser.add_argument('--suggest', action='store_true',
                        help='print nearest-method rename hints for drifted claims')
    parser.add_argument('--strict-symbols', action='store_true',
                        help='treat known (baselined) drift as a failure too')
    parser.add_argument('--baseline', metavar='PATH',
                        help='alternate drift baseline file')
    return parser.parse_args(argv)


def _index_or_skip():
    """The class index, or None when the book has no source tree to read."""
    print(f'Building class index from the configured source tree: {source_root()}')
    class_index = build_class_index()
    if not class_index:
        print(f'  [skip] H2 source tree not found at {source_root()}; '
              f'set [sources].src_main in data/config/config.json', file=sys.stderr)
        return None
    print(f'Indexed {len(class_index)} unique class names')
    print()
    return class_index


def _scan(class_index):
    """Reference checks that do not depend on the drift baseline."""
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
    claims = verify_symbol_claims(extract_symbol_claims(), class_index)
    return results, claims


def _prune(baseline_path: str, claims, version: str) -> int:
    """Drop accepted entries that resolve again; the rest stay."""
    accepted = set(load_baseline(baseline_path).get('accepted', []))
    kept = [(claim, rel) for claim, rel in claims
            if _claim_key(claim.doc_file, claim.class_name, claim.method) in accepted]
    dropped = len(accepted) - len(kept)
    save_baseline(kept, version, baseline_path)
    print(f'  baseline pruned: {dropped} resolved entr(ies) removed, {len(kept)} kept')
    return 0


def _record_baseline(baseline_path: str, claims, version: str) -> int:
    save_baseline(claims, version, baseline_path)
    print(f'  baseline updated: {len(claims)} accepted claim(s) '
          f'-> {os.path.relpath(baseline_file(), REPO_ROOT)}')
    return 0


def _print_drift(claims, new_drift, known_drift, args, class_index) -> None:
    if not claims:
        return
    print(f'  {len(claims)} symbol claim(s) not found in source: '
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


def _json_summary(results, new_drift, known_drift, failures: int) -> int:
    print(json.dumps({
        'references': len(results),
        'ok': sum(1 for r in results if r.status == 'OK'),
        'offset': sum(1 for r in results if r.status == 'OFFSET'),
        'missing': sum(1 for r in results if r.status == 'MISSING'),
        'symbol_new': len(new_drift),
        'symbol_known': len(known_drift),
    }, ensure_ascii=False, indent=2))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    baseline_path = args.baseline or baseline_file()
    version = get_project_version()
    try:
        class_index = _index_or_skip()
        if class_index is None:
            return 0
        results, claims = _scan(class_index)
        new_drift, known_drift = split_drift(claims, load_baseline(baseline_path))

        if args.prune:
            return _prune(baseline_path, claims, version)
        if args.update_baseline:
            return _record_baseline(baseline_path, claims, version)
        _print_drift(claims, new_drift, known_drift, args, class_index)

        failures = len(new_drift) + (len(known_drift) if args.strict_symbols else 0)
        if args.json:
            return _json_summary(results, new_drift, known_drift, failures)
        print()
        print()
        print_report(results, class_index)
        if failures:
            print(f'Symbol drift: {failures} claim(s) need review '
                  f'(run with --suggest for rename hints)')
            return 1
        return 0
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(_errors.run(main))
