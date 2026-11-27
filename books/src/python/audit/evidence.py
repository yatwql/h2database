#!/usr/bin/env python3
"""Evidence density: how much of a chapter a reader can check against the source.

`claims.py` judges one sentence; this judges a chapter. Three numbers say whether the
analysis is backed by the tree or merely sounds like it:

    coords      `path.ext:line` references per 1000 manuscript lines
    symbols     `Class.method(` claims per 1000 manuscript lines
    coverage    share of substantive paragraphs that carry either, or a `Class` in code

Thresholds live in `style.json [evidence]` and default to 0, which means *report only*:
the iteration that adds this measurement records where the book stands before any floor is
enforced. A threshold of 0 never fails; a positive one fails the chapter that is below it.

Modes:
  default   per-chapter numbers, marker of the threshold in force
  --json    the same numbers, machine-readable

Exit codes: 0 ok (or report-only), 1 a chapter is below a positive threshold.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil, _mdutil

SYMBOL_RE = re.compile(r"\b[A-Z]\w{2,}\.\w{2,}\s*\(")
CLASS_RE = re.compile(r"`[A-Z]\w{2,}`")
FENCE_RE = re.compile(r"^\s*```")
HEADING_RE = re.compile(r"^\s*#{1,6}\s")
TABLE_RE = re.compile(r"^\s*\|")
PARAGRAPH_MIN = 80


def thresholds() -> dict:
    """The floors in force, from the book's own policy."""
    table = _config.current().style_policy.get("evidence") or {}
    return {
        "coords": float(table.get("min_coords_per_1000_lines") or 0),
        "symbols": float(table.get("min_symbols_per_1000_lines") or 0),
        "coverage": float(table.get("min_paragraph_coverage_pct") or 0),
    }


def paragraphs(text: str) -> list[str]:
    """Substantive paragraphs: prose only, no fences, tables or headings."""
    out: list[str] = []
    buffer: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            buffer = []
            continue
        if in_fence or HEADING_RE.match(line) or TABLE_RE.match(line):
            continue
        if line.strip():
            buffer.append(line.strip())
            continue
        joined = " ".join(buffer).strip()
        if len(joined) >= PARAGRAPH_MIN:
            out.append(joined)
        buffer = []
    joined = " ".join(buffer).strip()
    if len(joined) >= PARAGRAPH_MIN:
        out.append(joined)
    return out


def measured(path: str) -> dict:
    """The three numbers for one manuscript file.

    A relative path is read from the book root, so a caller can name a chapter the way the
    manuscript does instead of carrying an absolute path around.
    """
    target = path if os.path.isabs(path) else os.path.join(_config.BOOK_ROOT, path)
    text = _fsutil.read_text(target)
    lines = max(len(text.splitlines()), 1)
    coords = len(_mdutil.source_ref_re(tuple(_config.source_suffixes())).findall(text))
    symbols = len(SYMBOL_RE.findall(text))
    bodies = paragraphs(text)
    backed = [body for body in bodies
              if _mdutil.source_ref_re(tuple(_config.source_suffixes())).search(body)
              or SYMBOL_RE.search(body) or CLASS_RE.search(body)]
    coverage = round(len(backed) * 100 / len(bodies)) if bodies else 0
    return {
        "lines": lines,
        "coords": coords,
        "symbols": symbols,
        "paragraphs": len(bodies),
        "coverage_pct": coverage,
        "coords_per_1000": round(coords * 1000 / lines, 1),
        "symbols_per_1000": round(symbols * 1000 / lines, 1),
    }


def measure() -> dict[str, dict]:
    """Per manuscript file, in reading order."""
    return {os.path.basename(path): measured(path)
            for path in _config.chapter_files(include_cover=False)}


def shortfalls(numbers: dict[str, dict], floors: dict) -> list[str]:
    """Chapters below a positive floor; a floor of 0 means report only."""
    out: list[str] = []
    for name, row in numbers.items():
        if floors["coords"] and row["coords_per_1000"] < floors["coords"]:
            out.append(f"{name}: {row['coords_per_1000']} coords/1000 lines "
                       f"(floor {floors['coords']})")
        if floors["symbols"] and row["symbols_per_1000"] < floors["symbols"]:
            out.append(f"{name}: {row['symbols_per_1000']} symbols/1000 lines "
                       f"(floor {floors['symbols']})")
        if floors["coverage"] and row["coverage_pct"] < floors["coverage"]:
            out.append(f"{name}: {row['coverage_pct']}% paragraphs backed "
                       f"(floor {floors['coverage']:.0f}%)")
    return out


def render(numbers: dict[str, dict], floors: dict, below: list[str]) -> str:
    active = any(floors.values())
    lines = ["# 依据密度（按章）", ""]
    lines.append("| 文件 | 行数 | 坐标 | 坐标/千行 | 符号/千行 | 段落依据率 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for name, row in numbers.items():
        lines.append(f"| `{name}` | {row['lines']} | {row['coords']} | "
                     f"{row['coords_per_1000']} | {row['symbols_per_1000']} | "
                     f"{row['coverage_pct']}% |")
    lines.append("")
    lines.append("阈值：" + ("未启用（只报数）" if not active else
                             f"坐标 {floors['coords']}/千行、符号 {floors['symbols']}/千行、"
                             f"段落依据率 {floors['coverage']:.0f}%"))
    for problem in below:
        lines.append(f"  FAIL {problem}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    numbers = measure()
    floors = thresholds()
    below = shortfalls(numbers, floors)
    if args.json:
        print(json.dumps({"files": numbers, "thresholds": floors, "below": below},
                         ensure_ascii=False, indent=2))
        return 1 if below else 0
    print(render(numbers, floors, below))
    return 1 if below else 0


if __name__ == "__main__":
    sys.exit(_errors.run(main, sys.argv[1:]))
