#!/usr/bin/env python3
"""Link and anchor audit for the manuscript.

Verifies every inline markdown link/image in the book:
  * relative file targets resolve to an existing file
  * ``#anchor`` fragments match a real heading (same rule as the HTML build)
  * external URLs and code-fence content are ignored

Exit codes:
  0  every link resolves
  1  at least one broken link or anchor

Usage:
  python links.py            # human-readable report
  python links.py --json     # machine-readable summary
  python links.py --target 'ch3*.md'
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import glob
import json
import os
import sys

from lib import _config, _errors, _fsutil, _mdutil

Violation = tuple[str, int, str, str, str]  # file, line, kind, target, detail

def _relative(path: str) -> str:
    return os.path.relpath(path, _config.MANUSCRIPT_DIR).replace(os.sep, '/')

def _resolve(path: str, target: str) -> str:
    """Resolve a link target relative to the file that contains it."""
    if target.startswith('/'):
        return os.path.normpath(os.path.join(_config.MANUSCRIPT_DIR, target.lstrip('/')))
    return os.path.normpath(os.path.join(os.path.dirname(path), target))

def audit_file(path: str, slug_cache: dict[str, set[str]]) -> list[Violation]:
    """Return every broken link found in ``path``."""
    out: list[Violation] = []
    text = _fsutil.read_text(path)

    # Strip fenced blocks so example links inside code are never reported.
    for chunk in _mdutil.split_fences(text):
        base_line = text[:text.find(chunk)].count('\n') + 1 if chunk else 1
        for offset, raw in enumerate(chunk.split('\n')):
            line_no = base_line + offset
            for _label, target in _mdutil.iter_links(raw):
                if _mdutil.is_external(target):
                    continue
                file_part, _, anchor = target.partition('#')

                if not file_part:
                    # Same-file anchor.
                    if anchor and anchor not in _own_slugs(path, slug_cache):
                        out.append((path, line_no, 'BROKEN_ANCHOR', target,
                                    'no heading with this anchor'))
                    continue

                resolved = _resolve(path, file_part)
                if not os.path.exists(resolved):
                    out.append((path, line_no, 'BROKEN_FILE', target,
                                f'missing {_relative(resolved) or resolved}'))
                    continue

                if anchor and resolved.endswith('.md'):
                    slugs = _own_slugs(resolved, slug_cache)
                    if anchor not in slugs:
                        out.append((path, line_no, 'BROKEN_ANCHOR', target,
                                    f'no heading #{anchor} in {_relative(resolved)}'))
    return out

def _own_slugs(path: str, cache: dict[str, set[str]]) -> set[str]:
    if path not in cache:
        cache[path] = _mdutil.heading_slugs(_fsutil.read_lines(path))
    return cache[path]

def target_files(pattern: str | None) -> list[str]:
    if pattern:
        return sorted(glob.glob(os.path.join(_config.MANUSCRIPT_DIR, pattern)))
    return [p for p in _config.all_manuscript_files() if os.path.isfile(p)]

def scan(pattern: str | None = None) -> list[Violation]:
    cache: dict[str, set[str]] = {}
    violations: list[Violation] = []
    for path in target_files(pattern):
        if not path.endswith('.md'):
            continue
        violations.extend(audit_file(path, cache))
    return violations

def render(violations: list[Violation]) -> None:
    print('=' * 72)
    print(f'链接与锚点审计  违规：{len(violations)}')
    print('=' * 72)
    for path, line, kind, target, detail in violations:
        print(f'  {_relative(path)}:{line}  [{kind}] {target}  ({detail})')

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    parser.add_argument('--target', metavar='GLOB', help='restrict to files matching GLOB')
    args = parser.parse_args(argv)

    violations = scan(args.target)

    if args.json:
        payload = {
            'count': len(violations),
            'violations': [
                {'file': _relative(p), 'line': line, 'kind': kind,
                 'target': target, 'detail': detail}
                for p, line, kind, target, detail in violations
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not violations else 1

    if not violations:
        print('✅ 所有链接与锚点均可解析')
        return 0

    render(violations)
    return 1

if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
