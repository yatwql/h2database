#!/usr/bin/env python3
"""Enforce the toolchain architecture constraints from docs/managements/technical.md.

Checks
  LAYER    import direction (lib <- ingest/manuscript/audit/render, no siblings)
  WRITE    audit/ and lib/ must not write to the repository
  CONFIG   scripts outside lib/ must not hardcode repository paths
  NAMING   no stdlib-clashing module names, no redundant audit prefixes,
           no underscore prefixes on CLI entry points
  EXIT     report scripts expose --json or document exit codes

Exit 1 on any finding.

Usage:
  python check_architecture.py
  python check_architecture.py --json
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYERS = ('core', 'ingest', 'manuscript', 'audit', 'render', 'app')
# Channels may only reach the domain through core/ (plus lib for display config).
CHANNELS = 'app'
CHANNEL_FORBIDDEN_LAYERS = ('ingest', 'manuscript', 'audit', 'render')
CHANNEL_FORBIDDEN_CALLS = ('subprocess', 'write_text', "'w'", '"w"')

# Who may import whom. Anything not listed is a violation; the matrix is the
# contract, the checks below only explain the breach.
DEPENDENCY_MATRIX: dict[str, frozenset[str]] = {
    'lib': frozenset(),
    'core': frozenset({'lib'}),
    'ingest': frozenset({'lib'}),
    'manuscript': frozenset({'lib'}),
    'audit': frozenset({'lib'}),
    'render': frozenset({'lib'}),
    'app': frozenset({'lib', 'core', 'app'}),
}
STDLIB_CLASH = {'types', 'html', 'json', 'logging', 'email', 'code', 'test', 'binascii'}
PATH_LITERALS = ('books/', 'data/manuscript', 'data/config', 'data/tmpl')
WRITE_CALLS = ('write_text', 'open(')  # kept for the human-readable rule text
WRITE_MODES = 'wax+'
# Entry points that are deliberately not a make.py step (ad-hoc inspection
# tools: they take their own arguments and never run as part of a pipeline).
# Entry points that are deliberately not a make.py step, with the reason they
# stand on their own: ad-hoc tools take their own arguments, a few are driven by
# the runner or by another module instead of the step table.
STANDALONE_ENTRY = frozenset({
    'render/print_pdf.py',        # ad-hoc: render a different document
    'render/pdf_from_html.py',    # ad-hoc: HTML -> PDF without the book pipeline
    'audit/book_quality.py',      # metric consumed by the scorecard
    'audit/prose_quality.py',     # metric consumed by the scorecard
    'audit/failure_extract.py',   # diagnostic: pull failures out of a log
    'test_report.py',             # ad-hoc: run the suite with a saved report
    'audit/review_packet.py',     # produces the failure packet, decides nothing
    'audit/order_dependence.py',  # slow tier, driven by check_runner --mode p2
    'audit/scorecard.py',         # dispatched by `make.py report`
    'audit/test_health.py',       # dispatched by `make.py report health`
    'manuscript/terms.py',        # annotates chapter lead-ins on demand
    'manuscript/case_studies.py',  # builds the appendix A outline on demand
    'manuscript/snapshot.py',     # imports and verifies read-only snapshots
    'manuscript/renumber.py',     # per-edition chapter renumbering on demand
})
WIRED_LAYERS = ('render', 'audit', 'ingest', 'manuscript')
# Commands that dispatch to a dedicated function in make.py instead of walking a
# step list, so their GROUPS entry is a routing label, not a step selection.
COMMAND_GROUPS = frozenset({'test', 'cover', 'report'})
MAKE_PY = os.path.join(PY_ROOT, 'make.py')


def layer_of(path: str, root: str | None = None) -> str:
    rel = os.path.relpath(path, root or PY_ROOT).replace(os.sep, '/')
    return rel.split('/')[0] if '/' in rel else ''


BOOK_IDENTITY_RE = re.compile(r'h2-source-code-analysis|H2 \u6570\u636e\u5e93\u5f15\u64ce')


def check_book_identity() -> list[str]:
    """The toolchain never names its first book.

    A book's identity lives in book.toml; a literal in the code turns a reusable
    toolchain into a one-off assembler and survives every rename the config makes.
    """
    problems: list[str] = []
    for path in scripts():
        if os.path.basename(path) == os.path.basename(__file__):
            continue  # this rule owns the pattern it searches for
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            if BOOK_IDENTITY_RE.search(line):
                problems.append(f'{os.path.relpath(path, PY_ROOT)}:{lineno}: book identity '
                                f'literal; read it from book.toml')
    return problems


def scripts() -> list[str]:
    return sorted(p for p in glob.glob(os.path.join(PY_ROOT, '**', '*.py'), recursive=True)
                  if '__pycache__' not in p)


def imports_of(path: str) -> list[str]:
    tree = ast.parse(_fsutil.read_text(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
            for alias in node.names:
                found.append(f'{node.module}.{alias.name}')
        elif isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
    return found


def write_calls(tree: ast.AST) -> list[int]:
    """Line numbers of calls that write files (open in a write mode, write_text)."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, 'id', None) or getattr(func, 'attr', None)
        if name == 'write_text':
            lines.append(node.lineno)
            continue
        if name != 'open' or len(node.args) < 2:
            continue
        mode = node.args[1]
        literal_write = (isinstance(mode, ast.Constant) and isinstance(mode.value, str)
                         and any(flag in mode.value for flag in WRITE_MODES))
        keyword_mode = any(kw.arg == 'mode' for kw in node.keywords)
        if literal_write or keyword_mode:
            lines.append(node.lineno)
    return lines


def check(path: str, root: str | None = None) -> list[str]:
    problems: list[str] = []
    rel = os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..'))
    layer = layer_of(path, root)
    name = os.path.basename(path)[:-3]
    source = _fsutil.read_text(path)
    tree = ast.parse(source)

    # DOCSTRING: every module says what it is (naming is not documentation)
    if ast.get_docstring(tree) is None and not path.endswith('__init__.py'):
        problems.append(f'{rel}: missing module docstring')

    # MATRIX: the dependency matrix is authoritative - allowed edges only
    allowed = DEPENDENCY_MATRIX.get(layer)
    if allowed is not None:
        for module in imports_of(path):
            head = module.split('.')[0]
            if head in DEPENDENCY_MATRIX and head != layer and head not in allowed:
                problems.append(
                    f'{rel}: layer "{layer}" may not import "{module}" '
                    f'(allowed: {sorted(allowed) or "none"})')

    # LAYER: no sibling imports, no dependencies on render from below
    for module in imports_of(path):
        head = module.split('.')[0]
        allowed_up = (layer == 'app' and head == 'core')
        if head in LAYERS and head != layer and not allowed_up:
            problems.append(f'{rel}: imports sibling layer "{module}"')
        if head == 'render' and layer in ('ingest', 'manuscript', 'audit', 'lib'):
            problems.append(f'{rel}: layer "{layer}" must not depend on render')

    # CHANNEL: channels carry no business logic - no engine imports, no writes,
    # no process spawning. They render, read keys and call core.actions.
    if layer == CHANNELS:
        for module in imports_of(path):
            head = module.split('.')[0]
            if head in CHANNEL_FORBIDDEN_LAYERS:
                problems.append(
                    f'{rel}: channel imports "{module}"; go through core.actions')
            if head in ('make',):
                problems.append(f'{rel}: channel must not drive make.py directly')
        for call in CHANNEL_FORBIDDEN_CALLS:
            if call in source:
                problems.append(f'{rel}: channel contains "{call}" (business logic)')

    # DIRECTION: core is a domain layer, it never depends on the channels
    if layer == 'core':
        for module in imports_of(path):
            if module.split('.')[0] == 'app':
                problems.append(f'{rel}: core must not depend on the channel layer')

    # WRITE: gates must not modify the manuscript or artifacts (baselines excepted)
    if layer == 'audit' and 'baseline' not in source:
        writers = write_calls(tree)
        if writers:
            problems.append(
                f'{rel}: "{layer}" layer must not write files (line {writers[0]})')

    # CONFIG: no hardcoded repository paths outside lib/ (the gate defines them)
    if layer != 'lib' and name != 'check_architecture':
        for literal in PATH_LITERALS:
            if f'"{literal}' in source or f"'{literal}" in source:
                problems.append(f'{rel}: hardcodes repository path "{literal}"')

    # NAMING
    if name in STDLIB_CLASH:
        problems.append(f'{rel}: module name "{name}" shadows a stdlib module')
    if layer == 'audit' and name != 'check_architecture' \
            and (name.startswith(('audit_', 'check_')) or name.endswith('_check')):
        problems.append(f'{rel}: redundant audit/check prefix or suffix')
    in_library_pkg = (os.sep + 'languages' + os.sep) in path or (os.sep + 'lib' + os.sep) in path
    if name.startswith('_') and not in_library_pkg and not path.endswith('__init__.py'):
        problems.append(f'{rel}: CLI entry point must not start with an underscore')

    # EXIT: report scripts expose --json
    if layer in ('audit',) and 'argument' in source and '--json' not in source:
        problems.append(f'{rel}: report script should support --json')
    return problems


SPAWN_CALLS = ('run', 'call', 'check_call', 'check_output', 'Popen', 'run_path')


def referenced_modules() -> set[str]:
    """Modules another file really drives: imported, or spawned as a program.

    A mention in a message or a docstring is not a wiring; only an import or a
    process spawn proves the file is reachable without a step-table entry.
    """
    root = os.path.join(_config.BOOK_ROOT, 'src', 'python')
    mentioned: set[str] = set()
    for path in glob.glob(os.path.join(root, '**', '*.py'), recursive=True):
        if os.path.normpath(path) == os.path.normpath(MAKE_PY):
            continue  # the step table declares wiring; it is not a driver
        try:
            tree = ast.parse(_fsutil.read_text(path))
        except (OSError, SyntaxError):
            continue
        # a module that spawns processes may hold its command list in string
        # constants, so every '.py' literal there counts as a wiring
        spawns = any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and any(alias.name.split('.')[0] in ('subprocess', 'runpy')
                    for alias in node.names)
            for node in ast.walk(tree))
        if spawns:
            for literal in ast.walk(tree):
                if isinstance(literal, ast.Constant) and isinstance(literal.value, str) \
                        and literal.value.endswith('.py'):
                    mentioned.add(os.path.basename(literal.value)[:-3])
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    mentioned.add(alias.name.split('.')[0])
                if isinstance(node, ast.ImportFrom) and node.module:
                    mentioned.add(node.module.split('.')[0])
            elif isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, 'id', None) or getattr(func, 'attr', None)
                if name not in SPAWN_CALLS:
                    continue
                for arg in node.args:
                    for literal in ast.walk(arg):
                        if isinstance(literal, ast.Constant) \
                                and isinstance(literal.value, str) \
                                and literal.value.endswith('.py'):
                            mentioned.add(os.path.basename(literal.value)[:-3])
    return mentioned


def declared_steps() -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """(step name -> script path, group -> member names) from make.py, by AST.

    make.py imports the whole toolchain, so it is parsed rather than imported:
    the gate has to stay importable from a bare checkout.
    """
    steps: dict[str, str] = {}
    groups: dict[str, tuple[str, ...]] = {}
    try:
        tree = ast.parse(_fsutil.read_text(MAKE_PY))
    except (OSError, SyntaxError):
        return steps, groups
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        if value is None:
            continue
        if target == 'STEPS' and isinstance(value, ast.List):
            for element in value.elts:
                if not isinstance(element, ast.Tuple) or len(element.elts) < 2:
                    continue
                name, script = element.elts[0], element.elts[1]
                if isinstance(name, ast.Constant) and isinstance(script, ast.Constant):
                    steps[str(name.value)] = str(script.value)
        elif target == 'GROUPS' and isinstance(value, ast.Dict):
            for key, item in zip(value.keys, value.values, strict=False):
                if not isinstance(key, ast.Constant) or not isinstance(item, ast.Tuple):
                    continue
                members = tuple(str(e.value) for e in item.elts if isinstance(e, ast.Constant))
                groups[str(key.value)] = members
    return steps, groups


def check_wiring(steps: dict[str, str] | None = None,
                 groups: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """Every CLI entry point is reachable, and every group names real steps.

    A script nobody calls still imports, still passes its own unit test and still
    reports OK when run by hand — it just never runs where it matters. Reachability
    is therefore a property of the wiring, not of the script.

    ``steps``/``groups`` are injectable so the rule can be proven on a mutated
    wiring instead of on the live make.py (a deletion in the real file would
    otherwise be needed to exercise the failure path).
    """
    if steps is None or groups is None:
        declared, declared_groups = declared_steps()
        steps = declared if steps is None else steps
        groups = declared_groups if groups is None else groups
    if not steps:
        return []
    wired = {os.path.normpath(script).replace(os.sep, '/') for script in steps.values()}
    mentioned = referenced_modules()
    problems: list[str] = []
    for path in scripts():
        rel = os.path.relpath(path, PY_ROOT).replace(os.sep, '/')
        if rel in wired or rel in STANDALONE_ENTRY or rel.endswith('__init__.py'):
            continue
        if rel.split('/')[0] not in WIRED_LAYERS:
            continue
        if os.path.basename(rel)[:-3] in mentioned:
            continue  # driven by another module, not by the step table
        source = _fsutil.read_text(path)
        if "'__main__'" not in source and '"__main__"' not in source:
            continue
        problems.append(f'{rel}: CLI entry point is not reachable '
                        f'(add it to STEPS/GROUPS, or to STANDALONE_ENTRY)')
    for group, members in groups.items():
        if group in COMMAND_GROUPS:
            continue
        for member in members:
            if member not in steps:
                problems.append(f'make.py: group "{group}" names unknown step "{member}"')
    return problems


def check_scripts(scripts_dir: str | None = None) -> list[str]:
    """Name convention for the top-level wrappers in books/scripts/.

    `check-*` verifies (exit code decides), `eval-*` measures, `new-*` generates
    a new book; the interactive and setup entry points keep their names. One
    pattern per file, so the directory itself documents what a script is for.
    """
    directory = scripts_dir or os.path.join(_config.BOOK_ROOT, 'scripts')
    allowed = ('bookctl', 'launch', 'bootstrap', 'check', 'eval', 'new',
               'test', 'release', 'install')
    problems: list[str] = []
    if not os.path.isdir(directory):
        return problems
    try:
        entries = sorted(os.listdir(directory))
    except OSError as exc:
        return [f'scripts/: cannot list the directory: {exc}']
    for name in entries:
        path = os.path.join(directory, name)
        if not os.path.isfile(path) or name.startswith('.'):
            continue
        stem = name.rsplit('.', 1)[0]
        if not name.endswith(('.sh', '.ps1')):
            if name != 'bookctl':
                problems.append(f'scripts/{name}: unexpected file (expected .sh/.ps1)')
            continue
        if not any(stem == prefix or stem.startswith(prefix + '-') for prefix in allowed):
            problems.append(
                f'scripts/{name}: name must start with one of {", ".join(allowed)}')
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    problems: list[str] = check_scripts()
    problems += check_wiring()
    problems += check_book_identity()
    for path in scripts():
        try:
            problems += check(path)
        except SyntaxError as exc:  # pragma: no cover - parse failures surface elsewhere
            problems.append(f'{os.path.relpath(path, PY_ROOT)}: {exc}')

    if args.json:
        print(json.dumps({'count': len(problems), 'problems': problems},
                         ensure_ascii=False, indent=2))
        return 0 if not problems else 1

    if not problems:
        print('✅ 架构约束通过')
        return 0
    print(f'架构约束问题 {len(problems)} 处：')
    for problem in problems:
        print(f'  - {problem}')
    return 1


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
