#!/usr/bin/env python3
"""Detect drift between documentation, configuration and the repository.

Each fact is declared once and must point at something real:

  PATH     a back-ticked repository path mentioned in a document does not exist
  SCRIPT   a script listed in the docs is not present in the toolchain
  CHAPTER  a chapter file name mentioned in a document is not a manuscript file
  CONFIG   a book.toml table names a chapter the chapter list does not carry
  LEVEL    a gate level is declared outside the testplan tables that own it

Version agreement is not checked here: `version_consistency` owns it.

Exit 1 on any finding.

Usage:
  python doc_drift.py            # report
  python doc_drift.py --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

REPO_ROOT = os.path.normpath(os.path.join(_config.BOOK_ROOT, '..'))
PATH_RE = re.compile(r'`((?:books|h2|\.github|src|scripts|data|docs)/[A-Za-z0-9_./*-]+)`')
SCRIPT_RE = re.compile(r'`([a-z_]+\.py)`')
CHAPTER_RE = re.compile(r'(?<![\w/-])((?:ch\d[\w-]*|appendix-[\w-]+|cover)\.md)')
LEVEL_RE = re.compile(r'^\**P[0-3]\**$')
# files whose job is to record what changed may name files that do not exist
LEDGER_DOCS = ('changelog.md', 'review-findings.md')
# testplan headings that own the gate-level axis; everywhere else the level is
# repeated, and a repeated level drifts from the one that is checked
LEVEL_SECTIONS = ('2.1', '2.2')
CHAPTER_TABLES = ('packages', 'titles', 'numbering', 'coverage')
MANAGEMENTS = os.path.join('docs', 'managements')


PLAN_ROOT = ('docs', 'plan')
PLAN_SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
PLAN_NUMBERED_RE = re.compile(r'(?:^|[-_])(?:plan|rf)[-_]?\d+')
PLAN_ALLOWED_FILES = ('design.md', 'plan.md', 'README.md')


def _plan_topic_findings(topic: str, name: str) -> list[tuple[str, str]]:
    """(path, detail) for one topic directory under docs/plan."""
    out: list[tuple[str, str]] = []
    try:
        files = sorted(os.listdir(topic))
    except OSError as exc:
        return [(topic, f'{name}: cannot read ({exc})')]
    if 'plan.md' not in files:
        out.append((topic, f'{name}: 缺少 plan.md（实施计划）'))
    for entry in files:
        stem = entry[:-3] if entry.endswith('.md') else entry
        if PLAN_NUMBERED_RE.search(stem) or not PLAN_SLUG_RE.match(stem):
            out.append((os.path.join(topic, entry),
                        f'{name}/{entry}: 文件名用小写连字符的语义名，不用编号'))
        elif entry.endswith('.md') and entry not in PLAN_ALLOWED_FILES:
            out.append((os.path.join(topic, entry),
                        f'{name}/{entry}: 只允许 design.md / plan.md / README.md'))
    return out


def check_plan_tree(book_root: str | None = None) -> list[dict]:
    """Iteration designs live under docs/plan/<topic>/ with semantic names.

    The tracker number is a key in `plan.md`, not a file name: a directory called
    `plan-6` says which ticket it belongs to but nothing about what it argues, and
    it stops being findable the moment the ticket closes. Every topic is one
    directory whose name is a lowercase hyphenated slug of the subject, holding
    `design.md` and/or `plan.md`. A `review-findings.md` item that needs detail
    follows the same rule.
    """
    root = os.path.join(book_root or _config.BOOK_ROOT, *PLAN_ROOT)
    if not os.path.isdir(root):
        return []
    pairs: list[tuple[str, str]] = []
    try:
        entries = sorted(os.listdir(root))
    except OSError as exc:
        pairs.append((root, f'cannot read ({exc})'))
        entries = []
    for name in entries:
        topic = os.path.join(root, name)
        if not os.path.isdir(topic):
            pairs.append((topic, f'{name}: plan 根下只放主题目录，不放散文件'))
        elif not PLAN_SLUG_RE.match(name) or PLAN_NUMBERED_RE.search(name):
            pairs.append((topic, f'{name}: 主题目录名用小写连字符的语义名，不用编号'))
        else:
            pairs.extend(_plan_topic_findings(topic, name))
    return [{'kind': 'PLANNAME', 'file': os.path.relpath(path, REPO_ROOT),
             'line': 1, 'detail': detail} for path, detail in pairs]


def doc_files() -> list[str]:
    files = glob.glob(os.path.join(_config.BOOK_ROOT, 'docs', '**', '*.md'), recursive=True)
    files.append(os.path.join(_config.BOOK_ROOT, 'README.md'))
    files.append(os.path.join(REPO_ROOT, 'CLAUDE.md'))
    return sorted({os.path.normpath(p) for p in files if os.path.isfile(p)})


def _repo_root(explicit: str | None = None) -> str:
    return explicit or REPO_ROOT


def _generated_prefixes() -> tuple[str, ...]:
    """Repository-relative prefixes of paths that exist only after setup/run.

    Books are built (`dist/`), set up (`.venv/`) and produce logs
    (`logs/`); none of those are in a fresh checkout, yet documentation may
    legitimately point at them.
    """
    repo = os.path.dirname(_config.BOOK_ROOT)
    logging_cfg = _config.POLICY.get('logging') or {}
    candidates = (
        _config.DIST_DIR,
        os.path.join(_config.BOOK_ROOT, '.venv'),
        os.path.join(_config.BOOK_ROOT, logging_cfg.get('dir', 'logs')),
    )
    prefixes = []
    for path in candidates:
        rel = os.path.relpath(path, repo).replace(os.sep, '/').rstrip('/')
        prefixes.append(rel + '/')
    return tuple(prefixes)


def _git_ignored(rel: str) -> bool:
    """Whether git ignores this path: by design absent from a clean checkout.

    `data/tmp/` and the optional key file are real locally and missing on CI, so
    a documented path must be judged against the repository, not this machine.
    """
    import subprocess

    # run from the repository root and hand git a repo-relative path, otherwise a
    # path that starts with books/ resolves to books/books/… and never matches
    repo = os.path.dirname(_config.BOOK_ROOT)
    try:
        proc = subprocess.run(['git', 'check-ignore', '-q', rel], cwd=repo,
                              check=False, capture_output=True)
    except OSError:  # pragma: no cover - git missing
        return False
    return proc.returncode == 0


def _exists(rel: str, repo_root: str | None = None) -> bool:
    # generated / runtime paths are absent from a fresh checkout; a reference may
    # name the directory itself (`books/.venv`) or something inside it
    for prefix in _generated_prefixes():
        if rel == prefix.rstrip('/') or rel.startswith(prefix):
            return True
    # paths inside the tool's own book resolve from books/, the rest from the repo
    book_relative = rel.split('/', 1)[0] in ('src', 'scripts', 'data', 'docs')
    root = _config.BOOK_ROOT if book_relative else _repo_root(repo_root)
    if '*' in rel:
        return bool(glob.glob(os.path.join(root, rel), recursive=True))
    if os.path.exists(os.path.join(root, rel)):
        return True
    return _git_ignored(os.path.join('books', rel) if book_relative else rel)


DIMENSION_RE = re.compile(r'^>\s*维度：\**(.+?)\**\s*$', re.MULTILINE)
# every management document states its job in the header, so a reader knows what
# the file owns and what it deliberately does not
LOCUS_RE = re.compile(r'^>\s*定位：', re.MULTILINE)
LOCUS_WINDOW = 15
MANAGEMENTS_REF_RE = re.compile(r'(?:\.\./managements/|managements/)[\w-]+\.md')
# a management document is registered either as an index-table row or as a line in
# the directory tree that folder.md owns; both surfaces must name the same set
INDEX_ROW_RE = re.compile(r'^\|\s*`([\w-]+\.md)`\s*\|')
TREE_ROW_RE = re.compile(r'^\s{2,}([\w-]+\.md)\s+#')
# the two ledgers number their entries and publish the next free number
NEXT_RE = re.compile(r'\b(plan|rf)-next\s*=\s*(\d+)')
ENTRY_RE = re.compile(r'\b(plan|rf)-(\d+)\b')
# a document that spells out the delivery pipeline, or the script-name prefixes,
# is quoting the orchestrator; both lists must be read from it, not retyped
DELIVER_GROUP_RE = re.compile(r"'deliver':\s*\(([^)]*)\)")
QUOTED_NAME_RE = re.compile(r"'([a-z_]+)'")
INLINE_TOKEN_RE = re.compile(r'`([a-z_]+)`')
ALLOWED_PREFIX_RE = re.compile(r'allowed\s*=\s*\(([^)]*)\)')
PREFIX_CLAIM_RE = re.compile(r'只允许([^。]{0,200})')
PREFIX_TOKEN_RE = re.compile(r'`([a-z][a-z-]*)\*?`')
TOOLS_ROOT = os.path.join('src', 'python')


def _book_source(*parts: str) -> str:
    """Text of a toolchain file, or empty when the book has none (fixtures)."""
    path = os.path.join(_config.BOOK_ROOT, TOOLS_ROOT, *parts)
    if not os.path.isfile(path):
        return ''
    return _fsutil.read_text(path)


def deliver_steps(make_py_text: str | None = None) -> list[str]:
    """The `deliver` group as the orchestrator declares it."""
    text = make_py_text if make_py_text is not None else _book_source('make.py')
    match = DELIVER_GROUP_RE.search(text)
    return QUOTED_NAME_RE.findall(match.group(1)) if match else []


def script_prefixes(architecture_text: str | None = None) -> list[str]:
    """The wrapper-name prefixes the architecture gate accepts."""
    text = (architecture_text if architecture_text is not None
            else _book_source('audit', 'check_architecture.py'))
    match = ALLOWED_PREFIX_RE.search(text)
    return QUOTED_NAME_RE.findall(match.group(1)) if match else []


def check_deliver(files: list[str] | None = None,
                  steps: list[str] | None = None) -> list[dict]:
    """A document quoting the delivery pipeline names the same steps, in order.

The orchestrator owns the order; a manual that repeats a shorter list promises
a delivery run that never happens.
    """
    declared = steps if steps is not None else deliver_steps()
    if not declared:
        return []
    wanted = set(declared)
    out = []
    for path in files if files is not None else doc_files():
        if os.path.basename(path) in LEDGER_DOCS:
            continue
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            quoted = [token for token in INLINE_TOKEN_RE.findall(line) if token in wanted]
            if len(quoted) < 2 or quoted == declared:
                continue
            out.append({'kind': 'DELIVER', 'file': os.path.relpath(path, REPO_ROOT),
                        'line': lineno,
                        'detail': 'deliver pipeline quoted as '
                                  + ' -> '.join(quoted)
                                  + ' (orchestrator: ' + ' -> '.join(declared) + ')'})
    return out


def check_prefixes(files: list[str] | None = None,
                   prefixes: list[str] | None = None) -> list[dict]:
    """A document naming the allowed wrapper prefixes names all of them.

check_architecture decides which prefixes `books/scripts/` accepts; a manual that
lists a subset rejects a script the gate happily accepts.
    """
    declared = sorted(prefixes if prefixes is not None else script_prefixes())
    if not declared:
        return []
    out = []
    for path in files if files is not None else doc_files():
        if os.path.basename(path) in LEDGER_DOCS:
            continue
        text = _fsutil.read_text(path)
        for match in PREFIX_CLAIM_RE.finditer(text):
            span = match.group(1)
            if '前缀' not in span and 'scripts/' not in span:
                continue
            quoted = sorted(set(PREFIX_TOKEN_RE.findall(span)))
            if len(quoted) < 2 or quoted == declared:
                continue
            out.append({'kind': 'PREFIX', 'file': os.path.relpath(path, REPO_ROOT),
                        'line': text[:match.start()].count('\n') + 1,
                        'detail': 'prefix list quoted as '
                                  + ', '.join(quoted)
                                  + ' (architecture gate: ' + ', '.join(declared) + ')'})
    return out


def management_files(managements_dir: str | None = None) -> list[str]:
    directory = managements_dir or os.path.join(_config.BOOK_ROOT, 'docs', 'managements')
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(directory, '*.md')))


def _registered(path: str, pattern: re.Pattern) -> tuple[list[str], list[dict]]:
    """Registered names, plus a finding for every name registered twice."""
    names: list[str] = []
    out: list[dict] = []
    for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
        match = pattern.match(line)
        if match is None:
            continue
        name = match.group(1)
        if name in names:
            out.append({'kind': 'INDEX', 'file': os.path.relpath(path, REPO_ROOT),
                        'line': lineno, 'detail': f'{name} registered twice'})
            continue
        names.append(name)
    return names, out


def _surface_findings(label: str, path: str, registered: list[str],
                      actual: list[str], out: list[dict]) -> None:
    rel = os.path.relpath(path, REPO_ROOT)
    for name in registered:
        if name not in actual:
            out.append({'kind': 'INDEX', 'file': rel, 'line': 1,
                        'detail': f'{label} names {name}, which does not exist'})
    for name in actual:
        if name not in registered:
            out.append({'kind': 'INDEX', 'file': rel, 'line': 1,
                        'detail': f'{label} does not register {name}'})


def check_locus(directory: str | None = None) -> list[dict]:
    """Each management document opens by stating what job it holds.

    The role of a document is the one thing a reader cannot infer from its name:
    two files can both be about quality and still own different things. Stating it
    in the header keeps the index honest and makes the boundary reviewable.
    """
    base = directory or os.path.join(_config.BOOK_ROOT, 'docs', 'managements')
    out: list[dict] = []
    for name in management_files(base):
        path = os.path.join(base, name)
        head = '\n'.join(_fsutil.read_lines(path)[:LOCUS_WINDOW])
        if LOCUS_RE.search(head) is None:
            out.append({'kind': 'LOCUS', 'file': os.path.relpath(path, REPO_ROOT),
                        'line': 1,
                        'detail': 'header must state "> 定位：本文负责什么、不负责什么"'})
    return out


def check_managements(directory: str | None = None) -> list[dict]:
    """The management directory and its two registries name the same set.

    Two surfaces claim to describe the same directory: the index table in
    README.md and the tree in folder.md. Both are compared with the directory
    itself, so a document cannot exist unlisted, be listed twice, or stay listed
    after it is gone.
    """
    base = directory or os.path.join(_config.BOOK_ROOT, 'docs', 'managements')
    actual = management_files(base)
    out: list[dict] = []
    for label, filename in (('index', 'README.md'), ('tree', 'folder.md')):
        path = os.path.join(base, filename)
        if not os.path.isfile(path):
            continue
        pattern = INDEX_ROW_RE if label == 'index' else TREE_ROW_RE
        registered, duplicate_rows = _registered(path, pattern)
        out += duplicate_rows
        _surface_findings(f'{filename} {label}', path, registered, actual, out)
    return out


def check_numbering(files: list[str] | None = None) -> list[dict]:
    """The published next-entry number is really the next one.

    A marker that falls behind hands out a number already used; one that runs
    ahead leaves a gap the ledger cannot explain. Both are silent until a
    reference collides.
    """
    docs = files or doc_files()
    used: dict[str, int] = {'plan': 0, 'rf': 0}
    markers: list[tuple[str, int, str, int]] = []
    for path in docs:
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            for family, value in NEXT_RE.findall(line):
                markers.append((family, int(value), path, lineno))
                continue
            for family, value in ENTRY_RE.findall(line):
                used[family] = max(used[family], int(value))
    out = []
    for family, value, path, lineno in markers:
        expected = used[family] + 1
        if value != expected:
            out.append({'kind': 'NUMBERING', 'file': os.path.relpath(path, REPO_ROOT),
                        'line': lineno,
                        'detail': f'{family}-next = {value}, expected {expected} '
                                  f'(max used {used[family]})'})
    return out


# the content standard travels between projects, so it may not name this project's
# scripts, configuration files or gate tables; only its writing-style twin is fair
STANDARD_DOC = 'content-standard.md'
STANDARD_ALLOWED_REF = 'style-guide'
PROJECT_REF_RE = re.compile(r'`([\w-]+\.(?:py|toml|json|yml))`|\b([\w-]+)\.md\b')


def check_standard(path: str | None = None) -> list[dict]:
    """The content standard stays portable.

    It claims to apply to any repository, so it may point at its writing-style twin
    and nothing else: a script name, a config file or a gate table would tie it to
    this toolchain and stop it from travelling.
    """
    target = path or os.path.join(_config.BOOK_ROOT, 'docs', 'managements', STANDARD_DOC)
    if not os.path.isfile(target):
        return []
    out: list[dict] = []
    for lineno, line in enumerate(_fsutil.read_lines(target), start=1):
        for script, doc in PROJECT_REF_RE.findall(line):
            if doc == STANDARD_ALLOWED_REF:
                continue
            detail = script or doc
            out.append({'kind': 'STANDARD', 'file': os.path.relpath(target, REPO_ROOT),
                        'line': lineno,
                        'detail': f'content standard names {detail}; a portable standard '
                                  f'may only point at {STANDARD_ALLOWED_REF}.md'})
    return out


# criterion documents state properties; the config carries the numbers and the key
# paths that locate them (technical §3.2), so a criteria table must not cite keys
CONFIG_KEY_MIN_LEN = 6


def config_keys() -> set[str]:
    """Every key name declared anywhere in the two JSON configuration inputs."""
    names: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and len(key) >= CONFIG_KEY_MIN_LEN:
                    names.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for name in ('base.json', 'style.json'):
        path = _config.config_path(name)
        if os.path.isfile(path):
            walk(_fsutil.load_json(path))
    return names


def check_threshold_keys(files: list[str] | None = None,
                         keys: set[str] | None = None) -> list[dict]:
    """The criteria table states a property, not the place the number lives.

    Citing a configuration key in a pass condition mixes two jobs: what counts as
    passing, and where the threshold is configured. The second belongs to the
    design document, which owns threshold ownership.
    """
    known = keys if keys is not None else config_keys()
    if not known:
        return []
    out = []
    for path in files if files is not None else doc_files():
        if os.path.basename(path) != 'testplan.md':
            continue
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            if not line.lstrip().startswith('|'):
                continue
            for token in INLINE_TOKEN_RE.findall(line):
                if token in known:
                    out.append({'kind': 'THRESHOLD',
                                'file': os.path.relpath(path, REPO_ROOT),
                                'line': lineno,
                                'detail': f'criteria cite the config key {token}; state the '
                                          f'property and leave the key to technical §3.2'})
    return out


def check_manual_scope(manual_dir: str | None = None) -> list[dict]:
    """User documents state their dimension once, and do not quote the design.

    A manual answers "how do I use this"; each one owns a single dimension so two
    manuals cannot drift into covering the same ground, and none of them leans on
    the requirements or the design documents to explain itself.
    """
    directory = manual_dir or os.path.join(_config.BOOK_ROOT, 'docs', 'manuals')
    out: list[dict] = []
    seen: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(directory, '*.md'))):
        rel = os.path.relpath(path, REPO_ROOT)
        text = _fsutil.read_text(path)
        match = DIMENSION_RE.search(text)
        if match is None:
            out.append({'kind': 'SCOPE', 'file': rel, 'line': 1,
                        'detail': 'manuals must declare "> 维度：" '})
            continue
        dimension = match.group(1).strip()
        if dimension in seen:
            out.append({'kind': 'SCOPE', 'file': rel, 'line': 1,
                        'detail': f'dimension duplicates {seen[dimension]}'})
        else:
            seen[dimension] = rel
        for lineno, line in enumerate(text.split('\n'), start=1):
            for ref in MANAGEMENTS_REF_RE.finditer(line):
                out.append({'kind': 'SCOPE', 'file': rel, 'line': lineno,
                            'detail': f'user document refers to the design docs: {ref.group(0)}'})
    return out


def check_paths(files: list[str], repo_root: str | None = None) -> list[dict]:
    out = []
    for path in files:
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            for match in PATH_RE.finditer(line):
                target = match.group(1)
                if '...' in target or '…' in target or '<' in target:
                    continue  # illustrative path
                if not _exists(target, repo_root):
                    out.append({'kind': 'PATH', 'file': os.path.relpath(path, REPO_ROOT),
                                'line': lineno, 'detail': target})
    return out


def check_scripts(files: list[str], book_root: str | None = None) -> list[dict]:
    base = book_root or _config.BOOK_ROOT
    # documented scripts live in the toolchain, and a contract may point at the
    # test that enforces it, so both trees count as known names
    available = set()
    for tree in ('python', 'test'):
        available |= {os.path.basename(p) for p in
                      glob.glob(os.path.join(base, 'src', tree, '**', '*.py'),
                                recursive=True)}
    out = []
    for path in files:
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            for match in SCRIPT_RE.finditer(line):
                name = match.group(1)
                if name not in available:
                    out.append({'kind': 'SCRIPT', 'file': os.path.relpath(path, REPO_ROOT),
                                'line': lineno, 'detail': name})
    return out


def check_chapters(files: list[str]) -> list[dict]:
    configured = set(_config.chapter_names())
    actual = {os.path.basename(p) for p in
              glob.glob(os.path.join(_config.MANUSCRIPT_DIR, '*.md'))}
    out = []
    for path in files:
        if os.path.basename(path) in LEDGER_DOCS:
            continue  # the changelog and the findings ledger cite old names on purpose
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            # a chapter name is wrong whether or not it is written in back-ticks:
            # a directory tree in a document names files just like prose does
            for name in CHAPTER_RE.findall(line):
                if name not in configured or name not in actual:
                    out.append({'kind': 'CHAPTER', 'file': os.path.relpath(path, REPO_ROOT),
                                'line': lineno, 'detail': name})
    return out


def check_config() -> list[dict]:
    """Every chapter keyed in a book.toml table must be in the chapter list.

    A table that names a file the reading order does not carry is a dead key: the
    renderer never reaches it, so the mapping it expresses is a lie nobody sees.
    """
    files = set(_config.chapter_names())
    config_rel = os.path.relpath(_config.CONFIG_PATH, REPO_ROOT)
    out = []
    for table in CHAPTER_TABLES:
        for key in _config.chapter_table(table):
            if key not in files:
                out.append({'kind': 'CONFIG', 'file': config_rel,
                            'line': 1,
                            'detail': f'[chapters.{table}] names {key}, '
                                      f'which [chapters] files does not carry'})
    return out


def check_levels(files: list[str]) -> list[dict]:
    """A gate level is declared in one table only.

    The level of a check has one owner: the testplan's own gate tables. A second
    table that restates levels drifts from that one silently, because nothing
    compares the two.
    """
    out = []
    for path in files:
        if os.path.basename(os.path.dirname(path)) != 'managements':
            continue
        owner = os.path.basename(path) == 'testplan.md'
        heading = ''
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            if line.startswith('#'):
                heading = line.lstrip('#').strip()
                continue
            if not line.lstrip().startswith('|'):
                continue
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if not any(LEVEL_RE.match(cell) for cell in cells):
                continue
            if owner and heading.startswith(LEVEL_SECTIONS):
                continue
            out.append({'kind': 'LEVEL', 'file': os.path.relpath(path, REPO_ROOT),
                        'line': lineno,
                        'detail': 'gate level belongs to testplan §2.1/§2.2: '
                                  + line.strip()[:48]})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    files = doc_files()
    findings = (check_paths(files) + check_scripts(files) + check_chapters(files)
                + check_config() + check_levels(files) + check_manual_scope()
                + check_managements() + check_numbering(files)
                + check_deliver(files) + check_prefixes(files) + check_locus()
                + check_standard() + check_threshold_keys(files) + check_plan_tree())

    if args.json:
        print(json.dumps({'count': len(findings), 'findings': findings},
                         ensure_ascii=False, indent=2))
        return 0 if not findings else 1

    if not findings:
        print('✅ 文档与仓库一致（无漂移）')
        return 0
    print(f'文档漂移 {len(findings)} 处：')
    for item in findings[:40]:
        print(f"  {item['file']}:{item['line']}  [{item['kind']}] {item['detail']}")
    return 1


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
