#!/usr/bin/env python3
"""Audit cross-references: every `详见第X章《...》` resolves, and no chapter is thin.

Two rules, both taken from the book's configuration:

  RESOLVES   the chapter exists and the title inside 《》 is that chapter's H1 title —
             otherwise the reader follows a pointer to nothing
  DENSITY    each chapter carries at least `chapters_min_cross_refs` references, so a
             chapter cannot be an island the rest of the book never sends the reader to

A reference count belongs to the chapter that carries it, not to the file: a chapter
may be one file, or a first file plus continuation files that declare no H1 of their
own and are attributed through the book's `[chapters.coverage]` table.

Exit codes:
    0  every reference resolves and every chapter meets the configured minimum
    1  a dangling reference, or a chapter below the minimum
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
import re

from lib import _config, _errors, _fsutil

_fsutil.pin_stdout_utf8()

H1_RE = re.compile(r"(?m)^# 第(\d+)章\s+(.+)$")
REF_RE = re.compile(r"详见第(\d+)章《([^》]+)》")


def chapter_files() -> list[str]:
    """Chapter files of the book being audited, read when the audit runs."""
    return _config.chapter_files(include_cover=False)


def chapter_titles() -> dict[int, tuple[str, str]]:
    """Chapter number -> (H1 title, file that declares it), in reading order."""
    titles: dict[int, tuple[str, str]] = {}
    for path in chapter_files():
        for line in _fsutil.read_lines(path):
            match = H1_RE.match(line.strip())
            if match:
                titles[int(match.group(1))] = (match.group(2).strip(), os.path.basename(path))
    return titles


def chapter_blocks() -> tuple[list[tuple[int, str, str]], list[str]]:
    """(chapter, file, text) for every chapter body, plus files it cannot attribute.

    A file that declares H1s holds one block per H1; a continuation file (no H1 of
    its own) is attributed through `[chapters.coverage]` when it names exactly one
    chapter, because that is the only case where the answer is not a guess.
    """
    blocks: list[tuple[int, str, str]] = []
    unattributed: list[str] = []
    coverage = _config.chapter_coverage()
    for path in chapter_files():
        name = os.path.basename(path)
        text = _fsutil.read_text(path)
        parts = re.split(r"(?m)^# 第(\d+)章", text)
        if len(parts) > 1:
            for index in range(1, len(parts) - 1, 2):
                blocks.append((int(parts[index]), name, parts[index + 1]))
            continue
        covered = [int(number) for number in coverage.get(name, [])]
        if len(covered) == 1:
            blocks.append((covered[0], name, text))
        elif covered:
            unattributed.append(name)
    return blocks, unattributed


def references() -> list[tuple[str, int, str]]:
    """(file, target chapter, target title) for every reference in the book."""
    found: list[tuple[str, int, str]] = []
    for path in chapter_files():
        name = os.path.basename(path)
        for match in REF_RE.finditer(_fsutil.read_text(path)):
            found.append((name, int(match.group(1)), match.group(2).strip()))
    return found


def report_titles(titles: dict[int, tuple[str, str]]) -> None:
    print("=== Chapter H1 Titles ===")
    for number in sorted(titles):
        title, name = titles[number]
        print(f'  ch{number}: "{title}" ({name})')


def report_resolution(
    found: list[tuple[str, int, str]], titles: dict[int, tuple[str, str]]
) -> list[tuple[str, int, str, str]]:
    """Print the resolution verdict; return the mismatches."""
    print(f"\n=== Cross-References Found: {len(found)} ===")
    errors: list[tuple[str, int, str, str]] = []
    for name, target, title in found:
        if target not in titles:
            errors.append((name, target, title, "CHAPTER_NOT_FOUND"))
        elif titles[target][0] != title:
            errors.append((name, target, title, titles[target][0]))
    if errors:
        print(f"\n=== MISMATCHES: {len(errors)} ===")
        for name, target, title, actual in errors:
            print(f'  {name}: ch{target} ref "{title}" -> actual "{actual}"')
    else:
        print("\n=== All cross-references match! ===")
    print(f"\nOK: {len(found) - len(errors)}, Errors: {len(errors)}")
    return errors


def report_density(minimum: int) -> list[tuple[int, int]]:
    """Print the per-chapter counts; return the chapters below the minimum."""
    blocks, unattributed = chapter_blocks()
    counts: dict[int, int] = {}
    files: dict[int, list[str]] = {}
    for number, name, text in blocks:
        counts[number] = counts.get(number, 0) + len(REF_RE.findall(text))
        files.setdefault(number, []).append(name)

    print(f"\n=== Per-chapter cross-reference density (minimum {minimum}) ===")
    below: list[tuple[int, int]] = []
    for number in sorted(counts):
        count = counts[number]
        names = ", ".join(dict.fromkeys(files[number]))
        print(f"  ch{number:<3} {count:>3} refs ({names})")
        if count < minimum:
            below.append((number, count))
    for name in unattributed:
        print(f"  INFO: {name} declares no chapter and covers several; not counted")
    if below:
        thin = ", ".join(f"ch{number}({count})" for number, count in below)
        print(f"  FAIL: below the configured minimum: {thin}")
    else:
        print(f"  OK: every chapter carries at least {minimum} cross-references")
    return below


def main(argv: list[str] | None = None) -> int:
    del argv  # the audit takes no options: the book is the configuration
    titles = chapter_titles()
    report_titles(titles)
    errors = report_resolution(references(), titles)
    minimum = int(_config.THRESHOLDS.get("chapters_min_cross_refs", 1))
    below = report_density(minimum)
    return 1 if errors or below else 0


if __name__ == "__main__":
    _sys.exit(_errors.run(main, _sys.argv[1:]))
