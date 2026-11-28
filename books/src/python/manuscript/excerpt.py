#!/usr/bin/env python3
"""Print, check and repair source excerpts.

A book about a source tree explains code by quoting it. Quoting by hand is where the two
failure modes live: the pasted lines drift from the tree, and the cited span stops
containing what is shown. This command makes both mechanical:

    excerpt.py --file org/example/Widget.java --lines 42-60
        print a ready-to-paste block: the citation head, the source lines, the fence

    excerpt.py --check <manuscript.md>
        report the excerpts that no longer match the span they cite

    excerpt.py --repair <manuscript.md>
        retarget a drifted excerpt to the span that actually holds its lines, and mark the
        gaps with `// ...`; the code itself is never rewritten

The verification rules are the ones `audit/content_depth.py` enforces, so a repaired block
cannot disagree with the gate that judges it.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil, _mdutil

HEAD_RE = re.compile(r"^(\s*)//\s*([\w.]+\.(?:java|py|rs|kt|go|c)):(\d+)(?:-(\d+))?\s*$")
FENCE_RE = re.compile(r"^\s*```(\w*)\s*$")
LANG_BY_SUFFIX = {
    ".java": "java",
    ".py": "python",
    ".rs": "rust",
    ".kt": "kotlin",
    ".go": "go",
    ".c": "c",
}
ELISION = "// ..."


def locate(name: str) -> str:
    """The source file for a citation: exact path first, then by basename."""
    root = _config.source_tree("src_main")
    direct = os.path.join(root, name)
    if os.path.isfile(direct):
        return direct
    base = os.path.basename(name)
    for folder, _dirs, files in os.walk(root):
        if base in files:
            return os.path.join(folder, base)
    raise SystemExit(f"error: {name} not found under {root}")


def code_of(line: str) -> str:
    """The code part of an excerpt line, without the annotated comment."""
    return _mdutil.excerpt_code(line).strip()


def is_elision(line: str) -> bool:
    return _mdutil.excerpt_is_elision(line)


def block(name: str, start: int, end: int | None = None) -> str:
    """A ready-to-paste excerpt block for one span."""
    lines = _fsutil.read_lines(locate(name))
    last = end or start
    if last < start or last > len(lines):
        raise SystemExit(f"error: {name} has {len(lines)} lines; cannot quote {start}-{last}")
    language = LANG_BY_SUFFIX.get(os.path.splitext(name)[1], "")
    body = [line.rstrip() for line in lines[start - 1 : last]]
    head = f"// {os.path.basename(name)}:{start}-{last}"
    return "\n".join([f"```{language}", head, *body, "```"])


def bodies(lines: list[str], index: int) -> tuple[list[str], int]:
    """(body, last index) of the fence that follows a citation head."""
    body: list[str] = []
    cursor = index + 1
    while cursor < len(lines):
        if FENCE_RE.match(lines[cursor]):
            if body:
                break
            cursor += 1
            continue
        body.append(lines[cursor].rstrip())
        cursor += 1
    while body and not body[-1].strip():
        body.pop()
    return body, cursor


def _same_line(shown: str, source: str) -> bool:
    """Whether the line shown is the source line (see `_mdutil.excerpt_line_matches`)."""
    return _mdutil.excerpt_line_matches(shown, source)


def drift_of(name: str, start: int, end: int | None, body: list[str]) -> str:
    """Empty when the excerpt matches its span, else the reason it does not."""
    source = [line.strip() for line in _fsutil.read_lines(locate(name))]
    shown = [code_of(row) for row in body if code_of(row)]
    elided = any(is_elision(row) for row in body)
    if end is None:
        if shown and (start - 1 >= len(source) or shown[0] != source[start - 1]):
            return "head line does not match the cited start"
        return ""
    span = source[start - 1 : end]
    if not span or len(span) != end - start + 1:
        return "the cited span is outside the file"
    if not elided:
        # blanks inside the block are part of the span, so compare the body as it stands
        whole = [row.strip() for row in body]
        if len(whole) != len(span) or any(
            not _same_line(a, b) for a, b in zip(whole, span, strict=False)
        ):
            return "the body is not the cited span"
        return ""
    cursor = 0
    for code in shown:
        while cursor < len(span) and span[cursor] != code:
            cursor += 1
        if cursor == len(span):
            return "a shown line is not inside the cited span"
        cursor += 1
    return ""


def check(path: str) -> list[str]:
    """Reasons the excerpts in one manuscript file no longer match their spans."""
    lines = _fsutil.read_lines(path)
    problems: list[str] = []
    for index, line in enumerate(lines):
        head = HEAD_RE.match(line)
        if not head:
            continue
        name, start = head.group(2), int(head.group(3))
        end = int(head.group(4)) if head.group(4) else None
        body, _last = bodies(lines, index)
        reason = drift_of(name, start, end, body)
        if reason:
            problems.append(
                f"{os.path.basename(path)}:{index + 1} {name}:{start}"
                f"{'-' + str(end) if end else ''} — {reason}"
            )
    return problems


def repair(path: str) -> int:
    """Retarget drifted excerpts to the span that holds their lines, marking gaps.

    The prose and the annotations stay; only the citation and the elisions change. A line
    that cannot be found anywhere in the source is left alone and reported — that is a
    content problem, not a citation problem.
    """
    lines = _fsutil.read_lines(path)
    changed = 0
    for index, line in enumerate(lines):
        head = HEAD_RE.match(line)
        if not head:
            continue
        name, start = head.group(2), int(head.group(3))
        end = int(head.group(4)) if head.group(4) else None
        body, last = bodies(lines, index)
        if not drift_of(name, start, end, body):
            continue
        source = [row.strip() for row in _fsutil.read_lines(locate(name))]
        codes = [code_of(row) for row in body if code_of(row)]
        positions, cursor, found = [], 0, True
        for code in codes:
            while cursor < len(source) and source[cursor] != code:
                cursor += 1
            if cursor == len(source):
                found = False
                break
            positions.append(cursor)
            cursor += 1
        if not found or not positions:
            print(f"  cannot retarget {name}: shown lines are not in the file")
            continue
        rebuilt: list[str] = []
        previous = None
        seen = 0
        for row in body:
            code = code_of(row)
            if code:
                position = positions[seen]
                seen += 1
                if previous is not None and position != previous + 1:
                    rebuilt.append(ELISION)
                previous = position
            rebuilt.append(row)
        indent = head.group(1)
        new_head = f"{indent}// {os.path.basename(name)}:{positions[0] + 1}-{positions[-1] + 1}"
        lines[index : last + 1] = [new_head, *rebuilt]
        changed += 1
    if changed:
        _fsutil.write_text(path, "\n".join(lines) + "\n")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--file", help="source file, relative to the analysed tree")
    parser.add_argument("--lines", help="line or span, e.g. 382 or 382-401")
    parser.add_argument("--check", metavar="MANUSCRIPT", help="verify a manuscript file")
    parser.add_argument("--repair", metavar="MANUSCRIPT", help="retarget drifted excerpts")
    args = parser.parse_args(argv)

    if args.repair:
        changed = repair(args.repair)
        print(f"repaired {changed} excerpt(s)")
        return 0
    if args.check:
        problems = check(args.check)
        for problem in problems:
            print(f"  {problem}")
        return 1 if problems else 0
    if not args.file or not args.lines:
        parser.error("give --file and --lines, or --check/--repair")
    start_text, _, end_text = args.lines.partition("-")
    print(block(args.file, int(start_text), int(end_text) if end_text else None))
    return 0


if __name__ == "__main__":
    sys.exit(_errors.run(main, sys.argv[1:]))
