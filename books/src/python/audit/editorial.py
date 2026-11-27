"""Editorial profile audit: does the manuscript actually carry the agreed elements?

Three elements are measurable without judging the prose, so they are measured:

    learning_goals   list items under the chapter's goals section
    pitfalls         entries under the chapter's pitfalls section
    table_density    markdown tables per 1000 lines of the chapter

The profile comes from the book (`data/book/editing.toml`); the ratio of what an element
should look like comes from `lib/_editorial.PRESETS`. Two verdicts are possible:

    ENABLED    the element is part of the profile, so the measured count is compared with
               the configured minimum
    OFF        the profile does not ask for it; the count is reported and never judged

Because a book that has just adopted a profile is short everywhere, the shortfall is
recorded once in `data/baselines/editorial.json` and the gate then fails only when a count
*drops* — the same ratchet the other per-file baselines use. Raising the profile is a
configuration change, and the baseline is re-recorded deliberately when the content lands.

Exit codes:
    0  every enabled element meets its minimum, or nothing fell below the recorded baseline
    1  an enabled element is short, or a chapter fell below its recorded count
"""

import json
import os
import os as _os
import re
import sys
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from typing import Any, cast

from lib import _config, _editorial, _errors, _fsutil

_fsutil.pin_stdout_utf8()

BASELINE_REL = "editorial.json"
LIST_ITEM_RE = re.compile(r"(?m)^\s*(?:[-*+]|\d+\.)\s+\S")
TABLE_ROW_RE = re.compile(r"(?m)^\s*\|.*\|\s*$")
HEADING_RE = re.compile(r"(?m)^(#{2,4})\s+(.+?)\s*$")


def baseline_path() -> str:
    """The recorded counts, resolved when the audit runs (never at import time)."""
    return os.path.join(_config.baseline_dir(), BASELINE_REL)


def section_items(text: str, heading: str) -> int:
    """Number of list items across every section naming `heading`.

    The label is searched inside the heading rather than compared to it: a real heading
    carries its number ("## 7.7 本章小结"), and the number is the chapter's business. A
    file may hold several chapters, so every matching section adds up.
    """
    total = 0
    for match in HEADING_RE.finditer(text):
        if heading not in match.group(2):
            continue
        rest = text[match.end() :]
        following = HEADING_RE.search(rest)
        # a following heading opens its own section, not this one
        total += len(LIST_ITEM_RE.findall(rest[: following.start()] if following else rest))
    return total


def blockquote_items(text: str, marker: str) -> int:
    """Bullet items in the blockquote block introduced by `marker`.

    Learning goals are a blockquote in this book's manuscript convention
    (`> **章节要点**:` followed by `> - …` lines), not a heading section, so they are
    counted where they actually live rather than demanding a second, duplicate section.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if marker not in line:
            continue
        found = 0
        for following in lines[index + 1:]:
            stripped = following.lstrip()
            if not stripped.startswith(">"):
                break
            if re.match(r">\s*[-*]\s+\S", stripped):
                found += 1
        return found
    return 0


def table_count(text: str) -> int:
    """Markdown tables: a header row followed by a separator row."""
    lines = text.splitlines()
    tables = 0
    for index, line in enumerate(lines[:-1]):
        if "|" in line and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[index + 1]):
            tables += 1
    return tables


def table_density(text: str) -> float:
    """Markdown tables per 1000 lines.

    The density is reported; the ratchet watches the count, because adding prose lowers
    the ratio without removing a single table, and that is not a regression.
    """
    return round(table_count(text) * 1000 / max(len(text.splitlines()), 1), 2)


def measure() -> dict:
    """Per chapter-file counts, plus the profile that decides what is judged."""
    profile = _editorial.load_profile()
    rules = cast(dict[str, dict[str, Any]], profile["rules"])
    rows: list[dict] = []
    # Reference matter (appendices) is listed but not judged: a publisher asks a chapter
    # for learning goals and a recap, not an appendix.
    coverage = _config.chapter_coverage()
    for path in _config.chapter_files(include_cover=False):
        name = os.path.basename(path)
        if not coverage.get(name):
            continue
        text = _fsutil.read_text(path)
        rows.append(
            {
                "file": name,
                "lines": len(text.splitlines()),
                "learning_goals": blockquote_items(
                    text, rules["learning_goals"]["heading"]
                ),
                "key_points": section_items(text, rules["key_points"]["heading"]),
                "pitfalls": section_items(text, rules["pitfalls"]["heading"]),
                "tables": table_count(text),
            "table_density": table_density(text),
            }
        )
    return {
        "profile": profile["profile"],
        "rules": rules,
        "files": rows,
        "problems": list(cast(list[str], profile["problems"])),
    }


def shortfalls(metrics: dict) -> list[str]:
    """Enabled elements whose counts are below the configured minimum."""
    rules = metrics["rules"]
    problems: list[str] = []
    for row in metrics["files"]:
        for element in ("learning_goals", "key_points", "pitfalls"):
            rule = rules[element]
            if not rule.get("enabled"):
                continue
            minimum = int(rule.get("min_items", 1))
            if row[element] < minimum:
                problems.append(f"{row['file']}: {element} has {row[element]} of {minimum}")
        rule = rules["table_density"]
        if rule.get("enabled") and row["table_density"] < float(rule.get("min_per_1000_lines", 0)):
            problems.append(
                f"{row['file']}: table_density {row['table_density']} of "
                f"{rule['min_per_1000_lines']} per 1000 lines"
            )
    return problems


def regressions(metrics: dict, baseline: dict) -> list[str]:
    """Chapters whose count fell below the recorded baseline."""
    recorded = {row["file"]: row for row in baseline.get("files", [])}
    problems: list[str] = []
    for row in metrics["files"]:
        before = recorded.get(row["file"])
        if before is None:
            continue
        for element in ("learning_goals", "key_points", "pitfalls", "tables"):
            if row[element] < before[element]:
                problems.append(
                    f"{row['file']}: {element} fell from {before[element]} to {row[element]}"
                )
    return problems


def render(metrics: dict) -> str:
    rules = metrics["rules"]
    lines = [f"# 编辑要素度量（风格档：{metrics['profile']}）", ""]
    lines.append("| 元素 | 状态 | 下限 |")
    lines.append("| --- | --- | --- |")
    for element, label in (
        ("learning_goals", "学习目标"),
        ("key_points", "要点回顾"),
        ("pitfalls", "常见误区"),
    ):
        rule = rules[element]
        state = "必选" if rule.get("enabled") else "本档未启用"
        lines.append(f"| {label} | {state} | {rule.get('min_items', 1)} 条 |")
    rule = rules["table_density"]
    state = "必选" if rule.get("enabled") else "本档未启用"
    lines.append(f"| 表格密度 | {state} | {rule.get('min_per_1000_lines', 0)} 张/千行 |")
    lines.append("")
    lines.append("| 文件 | 行数 | 学习目标 | 要点回顾 | 常见误区 | 表格密度 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for row in metrics["files"]:
        lines.append(
            f"| `{row['file']}` | {row['lines']} | {row['learning_goals']} | "
            f"{row['key_points']} | {row['pitfalls']} | {row['table_density']} |"
        )
    return "\n".join(lines) + "\n"


def save_baseline(metrics: dict) -> None:
    payload = {
        "note": "Recorded editorial element counts. A count may rise, never fall.",
        "profile": metrics["profile"],
        "files": [
            {
                key: row[key]
                for key in (
                    "file",
                    "lines",
                    "learning_goals",
                    "key_points",
                    "pitfalls",
                    "tables",
                    "table_density",
                )
            }
            for row in metrics["files"]
        ],
    }
    _fsutil.ensure_dir(baseline_path())
    try:
        with open(baseline_path(), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    except OSError as exc:
        raise SystemExit(f"error: cannot write {baseline_path()}: {exc}") from exc


def load_baseline() -> dict:
    try:
        with open(baseline_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    metrics = measure()
    print(render(metrics))
    for problem in metrics["problems"]:
        print(f"  configuration: {problem}")
    if "--update-baseline" in args:
        save_baseline(metrics)
        print(f"baseline written: {baseline_path()}")
        return 0
    baseline = load_baseline()
    regress = regressions(metrics, baseline)
    short = shortfalls(metrics)
    if not baseline:
        for problem in short:
            print(f"  FAIL {problem}")
        print("  (no baseline yet: record the current state with --update-baseline once)")
        return 1 if short else 0
    for problem in short:
        print(f"  TODO {problem}  (recorded as an accepted shortfall; a count may not fall)")
    if regress:
        for problem in regress:
            print(f"  FAIL {problem}")
        return 1
    print("OK: nothing fell below the baseline")
    return 0


if __name__ == "__main__":
    sys.exit(_errors.run(main, sys.argv[1:]))
