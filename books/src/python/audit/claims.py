#!/usr/bin/env python3
"""Strong assertions must carry evidence.

A book about a source tree makes claims: *always*, *never*, *guarantees*, *the only*,
*the root cause*. Those are the sentences a reader trusts, and the ones that are cheapest to
get wrong — a book can be well formed, well captioned and still assert things the source
does not say. This gate asks one question per sentence:

    does this strong claim point at something a reader could check —
    a `path.ext:line` coordinate, a `Class.method(` symbol, or a backticked class?

It is a ratchet, not a target. The first measurement records today's count (mostly
unevidenced), and the gate fails only when a file's count *rises*: new prose must bring its
evidence, old prose is a recorded debt.

Modes:
  default            per-file counts, and whether anything rose above the baseline
  --list             the findings themselves, with file and line
  --json             machine-readable counts and findings
  --update-baseline  record the current counts (reviewed change)

Exit codes: 0 ok, 1 a count rose (or the baseline is missing and there are findings), 2 usage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _baseline, _config, _errors, _fsutil

BASELINE_KEY = "claims"
FENCE_RE = re.compile(r"^\s*```")
HEADING_RE = re.compile(r"^\s*#{1,6}\s")
TABLE_RE = re.compile(r"^\s*\|")
QUOTE_RE = re.compile(r"^\s*>")
COORDINATE_RE = re.compile(r"[\w/.-]+\.(?:java|py|rs|kt|go|c):\d+")
SYMBOL_RE = re.compile(r"\b[A-Z]\w{2,}\.\w{2,}\s*\(")
CLASS_RE = re.compile(r"`([A-Z]\w{2,})`")
# Defaults; a book may replace them through `style.json [claims]`.
DEFAULT_MARKERS = (
    "总是",
    "从不",
    "绝不",
    "必然",
    "一定",
    "唯一",
    "保证了",
    "避免了",
    "杜绝",
    "根本原因",
    "不可能",
    "永远",
)
# A sentence whose subject is a figure is evidence by pointing at the figure; judging the
# lead-in as an unsupported claim would report every caption in the book.
FIGURE_LEADINS = ("如图", "下图", "上图", "该图", "此图")


def markers() -> tuple[str, ...]:
    """The words that make a sentence a claim, from the book's own policy."""
    table = _config.current().style_policy.get("claims") or {}
    words = table.get("markers") or DEFAULT_MARKERS
    return tuple(str(word) for word in words)


def baseline_path() -> str:
    """Where the recorded counts live, resolved through this book's declarations.

    Resolved against the active book here rather than through `lib._baseline`: that module
    keeps the `_config` it was imported with, and in a long-lived process (tests, the TUI)
    the active book can change after the import — the file would then be written to the
    previous book's directory.
    """
    declared = (_config.BASE_POLICY.get("baselines") or {}).get(BASELINE_KEY) or ""
    if declared:
        return os.path.join(_config.BOOK_ROOT, declared)
    return os.path.join(_config.baseline_dir(), f"{BASELINE_KEY}.json")


def prose_sentences(text: str) -> list[tuple[int, str]]:
    """(line number, sentence) for running prose: fences, tables and headings are out.

    Code is not prose and a table cell is not a sentence; judging either would report the
    book's listings as unevidenced claims. Blockquotes are kept: the chapter lead is prose a
    reader trusts just as much.
    """
    endings = _config.sentence_endings()
    out: list[tuple[int, str]] = []
    in_fence = False
    buffer, started = "", 0
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            buffer = ""
            continue
        if in_fence or HEADING_RE.match(line) or TABLE_RE.match(line):
            continue
        stripped = QUOTE_RE.sub("", line).strip() if not line.startswith("#") else line
        if not stripped:
            if buffer:
                out.append((started, buffer.strip()))
                buffer = ""
            continue
        if not buffer:
            started = number
        buffer += stripped
        if stripped and stripped[-1] in endings:
            out.append((started, buffer.strip()))
            buffer = ""
    if buffer.strip():
        out.append((started, buffer.strip()))
    return out


def has_evidence(sentence: str) -> bool:
    """Whether a sentence points at something the reader can look up."""
    return bool(
        COORDINATE_RE.search(sentence) or SYMBOL_RE.search(sentence) or CLASS_RE.search(sentence)
    )


def findings() -> dict[str, list[dict]]:
    """Unevidenced claims per manuscript file, in reading order."""
    words = markers()
    out: dict[str, list[dict]] = {}
    for path in _config.chapter_files(include_cover=True):
        name = os.path.basename(path)
        hits: list[dict] = []
        for line, sentence in prose_sentences(_fsutil.read_text(path)):
            if sentence.lstrip().startswith(FIGURE_LEADINS):
                continue
            if not any(word in sentence for word in words):
                continue
            if has_evidence(sentence):
                continue
            hits.append({"line": line, "text": sentence[:160]})
        if hits:
            out[name] = hits
    return out


def measure() -> dict:
    found = findings()
    return {
        "files": {name: len(hits) for name, hits in sorted(found.items())},
        "total": sum(len(hits) for hits in found.values()),
    }


def load_baseline() -> dict:
    return _baseline.load_at(baseline_path())


def regressions(current: dict, baseline: dict) -> list[str]:
    """Files whose unevidenced-claim count rose above the recorded one."""
    recorded = baseline.get("files") or {}
    out: list[str] = []
    for name, count in current["files"].items():
        before = int(recorded.get(name, 0) or 0)
        if count > before:
            out.append(f"{name}: {count} unevidenced claims (baseline {before})")
    return out


def render(current: dict, rose: list[str]) -> str:
    lines = [f"# 强断言依据检查（{len(markers())} 个断言词）", ""]
    lines.append(
        f"- 未带依据的强断言：**{current['total']}** 条，分布在 {len(current['files'])} 个文件"
    )
    for name, count in sorted(current["files"].items(), key=lambda item: -item[1])[:10]:
        lines.append(f"  - `{name}`：{count} 条")
    if rose:
        lines.append("")
        for problem in rose:
            lines.append(f"  FAIL {problem}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list", action="store_true", help="print the findings")
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args(argv)

    current = measure()
    found = findings()
    if args.update_baseline:
        path = _baseline.save_at(
            baseline_path(),
            {"files": current["files"], "total": current["total"]},
            note="Unevidenced strong claims per file; may only fall.",
            gate=BASELINE_KEY,
            kind="counts",
            keyed_by="manuscript-path",
        )
        print(f"baseline written: {path}")
        return 0
    baseline = load_baseline()
    recorded = bool(baseline.get("files"))
    # without a recorded count there is nothing to compare against: the run reports the
    # findings and asks for the baseline rather than calling every finding a regression
    rose = regressions(current, baseline) if recorded else []
    if args.json:
        print(
            json.dumps(
                {"counts": current, "regressions": rose, "findings": found},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if rose else 0
    print(render(current, rose))
    if args.list:
        for name, hits in found.items():
            for hit in hits:
                print(f"  {name}:{hit['line']}  {hit['text']}")
    if rose:
        return 1
    if not recorded and current["total"]:
        print("  (no baseline yet: record today's count with --update-baseline)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_errors.run(main, sys.argv[1:]))
