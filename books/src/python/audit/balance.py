#!/usr/bin/env python3
"""Balance metrics for the H2 source-code analysis book.

Outputs per-chapter file metrics and an aggregate balance report:
  - Lines (raw line count of each source file)
  - Figures (count of `**图 X-Y: …**` captions)
  - Source refs (count of `.java:NNN` references)
  - Term hits (glossary entries whose `（第N章）` chapter ref matches)
  - Index hits (index entries referencing this chapter via §X.Y or 第N章)

Aggregate metrics:
  - Max / min line counts
  - max_min_ratio = max(lines) / min(lines)
  - Standard deviation of line counts

Modes:
  default            Pretty markdown table to stdout.
  --baseline FILE    Write a JSON snapshot to FILE for future diffs.
  --diff FILE        Compare current state against a baseline JSON file.
  --json             Emit machine-readable JSON to stdout (no markdown).

Usage examples:
  python books/tools/balance.py
  python books/tools/balance.py --baseline books/docs/managements/baseline-v5.0.json
  python books/tools/balance.py --diff books/docs/managements/baseline-v5.0.json
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import json
import math
import os
import re
import sys
from typing import Any

from lib import _config, _errors, _fsutil, _mdutil

_fsutil.pin_stdout_utf8()

MS_DIR = _config.MANUSCRIPT_DIR

# 章节文件 → 该文件覆盖的章节号集合（用于术语/索引命中归属）。
# 双章文件按其内含章节展开；ch6 三个子文件均归属"第6章"。

# Chapter numbering and file list come from book.toml (via _config).
CHAPTER_FILES: list[tuple[str, list[int]]] = [
    (os.path.basename(path), _config.chapter_coverage().get(os.path.basename(path), []))
    for path in _config.chapter_files(include_cover=False)
]

GLOSSARY_REL = "back/glossary.md"
INDEX_REL = "back/index.md"

# 匹配 glossary 条目末尾的 "（第N章 ...）" 章节标注；允许跟 § 子节或顿号。
GLOSSARY_CHAPTER_RE = re.compile(r"第(\d+)章")
# 匹配 index 条目右侧的 "§X.Y" 或 "第X章"；左侧是 — 分隔。
INDEX_CHAPTER_RE = re.compile(r"§(\d+)\.|第(\d+)章")


def count_lines(text: str) -> int:
    return len(text.splitlines())


def count_figures(text: str) -> int:
    return len(_mdutil.FIGURE_LINE_RE.findall(text))


def count_source_refs(text: str) -> int:
    return len(_mdutil.source_ref_re(tuple(_config.source_suffixes())).findall(text))


def load_glossary_chapter_index() -> dict[int, int]:
    """Return {chapter_number: count_of_terms_referencing_that_chapter}.

    v6.0 introduces multi-line glossary entries where the chapter reference
    lives on a separate `**章节**：第N章 §X.Y` continuation line. Walk
    entries as blocks delimited by `- **Term**:` markers and accumulate any
    chapter numbers found within each block.
    """
    path = os.path.join(MS_DIR, GLOSSARY_REL)
    counts: dict[int, int] = {}
    if not os.path.exists(path):
        return counts
    lines = _fsutil.read_lines(path)

    current_block: list[str] = []
    in_entry = False

    def flush(block: list[str]):
        if not block:
            return
        joined = "\n".join(block)
        # A term may reference multiple chapters; +1 per (entry, chapter) pair.
        chapters = {int(c) for c in GLOSSARY_CHAPTER_RE.findall(joined)}
        for ch in chapters:
            counts[ch] = counts.get(ch, 0) + 1

    for raw in lines:
        stripped = raw.lstrip()
        is_entry_start = stripped.startswith("- **")
        is_boundary = raw.strip().startswith("## ") or raw.strip().startswith("---")

        if is_entry_start:
            flush(current_block)
            current_block = [raw]
            in_entry = True
        elif is_boundary:
            flush(current_block)
            current_block = []
            in_entry = False
        elif in_entry:
            current_block.append(raw)

    flush(current_block)
    return counts


def load_index_chapter_index() -> dict[int, int]:
    """Return {chapter_number: count_of_index_entries_referencing_that_chapter}."""
    path = os.path.join(MS_DIR, INDEX_REL)
    counts: dict[int, int] = {}
    if not os.path.exists(path):
        return counts
    text = _fsutil.read_text(path)
    for line in text.splitlines():
        if not line.lstrip().startswith("- "):
            continue
        # 一行可能含多个引用（如 "§9.6, §6.4"），全部计入。
        for primary, secondary in INDEX_CHAPTER_RE.findall(line):
            ch_str = primary or secondary
            ch = int(ch_str)
            counts[ch] = counts.get(ch, 0) + 1
    return counts


def collect_metrics() -> dict[str, Any]:
    glossary_by_chapter = load_glossary_chapter_index()
    index_by_chapter = load_index_chapter_index()

    files: list[dict[str, Any]] = []
    for rel, chapters in CHAPTER_FILES:
        path = os.path.join(MS_DIR, rel)
        if not os.path.exists(path):
            continue
        text = _fsutil.read_text(path)
        lines = count_lines(text)
        figs = count_figures(text)
        refs = count_source_refs(text)
        term_hits = sum(glossary_by_chapter.get(c, 0) for c in chapters)
        index_hits = sum(index_by_chapter.get(c, 0) for c in chapters)
        files.append(
            {
                "file": rel,
                "chapters": chapters,
                "lines": lines,
                "figures": figs,
                "source_refs": refs,
                "term_hits": term_hits,
                "index_hits": index_hits,
            }
        )

    line_counts = [f["lines"] for f in files]
    fig_total = sum(f["figures"] for f in files)
    ref_total = sum(f["source_refs"] for f in files)

    if line_counts:
        max_lines = max(line_counts)
        min_lines = min(line_counts)
        ratio = max_lines / min_lines if min_lines else 0.0
        mean = sum(line_counts) / len(line_counts)
        var = sum((n - mean) ** 2 for n in line_counts) / len(line_counts)
        stddev = math.sqrt(var)
    else:
        max_lines = min_lines = 0
        ratio = 0.0
        mean = stddev = 0.0

    return {
        "files": files,
        "totals": {
            "files": len(files),
            "lines": sum(line_counts),
            "figures": fig_total,
            "source_refs": ref_total,
            "glossary_entries_total": sum(glossary_by_chapter.values()),
            "index_entries_total": sum(index_by_chapter.values()),
        },
        "balance": {
            "max_lines": max_lines,
            "min_lines": min_lines,
            "max_min_ratio": round(ratio, 3),
            "mean_lines": round(mean, 1),
            "stddev_lines": round(stddev, 1),
        },
    }


def render_markdown(metrics: dict[str, Any]) -> str:
    out: list[str] = []
    out.append("# 章节均衡度量报告")
    out.append("")
    out.append("## 各章节文件")
    out.append("")
    out.append("| 文件 | 章 | 行数 | 图数 | 源引用 | 术语命中 | 索引命中 |")
    out.append("|------|----|------|------|--------|---------|---------|")
    for f in metrics["files"]:
        ch = ",".join(str(c) for c in f["chapters"])
        out.append(
            f"| `{f['file']}` | {ch} | {f['lines']:,} | {f['figures']} | "
            f"{f['source_refs']} | {f['term_hits']} | {f['index_hits']} |"
        )
    out.append("")

    t = metrics["totals"]
    b = metrics["balance"]
    out.append("## 汇总")
    out.append("")
    out.append(f"- 文件数：{t['files']}")
    out.append(f"- 总行数：{t['lines']:,}")
    out.append(f"- 总图数：{t['figures']}")
    out.append(f"- 总源引用：{t['source_refs']}")
    out.append(f"- glossary 条目总数（按章累计）：{t['glossary_entries_total']}")
    out.append(f"- index 条目总数（按章累计）：{t['index_entries_total']}")
    out.append("")
    out.append("## 均衡指标")
    out.append("")
    out.append(f"- 最大行数：{b['max_lines']:,}")
    out.append(f"- 最小行数：{b['min_lines']:,}")
    out.append(
        f"- max_min_ratio：**{b['max_min_ratio']}**（v6.0 目标 ≤ 2.5；ch7-8 拆分后预期 ≈ 2.7）"
    )
    out.append(f"- 平均行数：{b['mean_lines']}")
    out.append(f"- 标准差：{b['stddev_lines']}")
    return "\n".join(out) + "\n"


def render_diff(current: dict[str, Any], baseline: dict[str, Any]) -> str:
    out: list[str] = []
    out.append("# 均衡度量 — 对照基线")
    out.append("")
    cur_files = {f["file"]: f for f in current["files"]}
    base_files = {f["file"]: f for f in baseline["files"]}
    all_files = sorted(set(cur_files) | set(base_files))

    out.append("| 文件 | 行数变化 | 图数变化 | 源引用变化 | 术语变化 | 索引变化 |")
    out.append("|------|---------|---------|-----------|---------|---------|")

    def delta(cur: dict | None, base: dict | None, key: str) -> str:
        c = cur.get(key, 0) if cur else 0
        b = base.get(key, 0) if base else 0
        d = c - b
        if d == 0:
            return f"{c}"
        sign = "+" if d > 0 else ""
        return f"{c} ({sign}{d})"

    for fname in all_files:
        cur = cur_files.get(fname)
        base = base_files.get(fname)
        marker = ""
        if cur and not base:
            marker = " 🆕"
        elif base and not cur:
            marker = " ❌"
        out.append(
            f"| `{fname}`{marker} | {delta(cur, base, 'lines')} | "
            f"{delta(cur, base, 'figures')} | {delta(cur, base, 'source_refs')} | "
            f"{delta(cur, base, 'term_hits')} | {delta(cur, base, 'index_hits')} |"
        )
    out.append("")

    cb = current["balance"]
    bb = baseline["balance"]
    out.append("## 均衡指标对照")
    out.append("")
    out.append(f"- max_min_ratio：{bb['max_min_ratio']} → **{cb['max_min_ratio']}**")
    out.append(f"- 标准差：{bb['stddev_lines']} → {cb['stddev_lines']}")
    out.append(f"- 最大行数：{bb['max_lines']:,} → {cb['max_lines']:,}")
    out.append(f"- 最小行数：{bb['min_lines']:,} → {cb['min_lines']:,}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--baseline", metavar="FILE", help="写入 JSON 基线快照到 FILE")
    p.add_argument("--diff", metavar="FILE", help="对比当前状态与 baseline JSON 文件")
    p.add_argument("--json", action="store_true", help="向 stdout 输出 JSON（机读）")
    args = p.parse_args(argv)

    metrics = collect_metrics()

    if args.diff:
        if not os.path.exists(args.diff):
            print(f"❌ 基线文件不存在：{args.diff}", file=sys.stderr)
            return 1
        baseline = _fsutil.load_json(args.diff)
        print(render_diff(metrics, baseline))
        return 0

    if args.baseline:
        _fsutil.ensure_dir(args.baseline)
        _fsutil.dump_json(args.baseline, metrics)
        print(f"✅ 基线已保存：{args.baseline}")
        print(
            f"   {metrics['totals']['files']} 个文件 · "
            f"{metrics['totals']['lines']:,} 行 · "
            f"max_min_ratio={metrics['balance']['max_min_ratio']}"
        )
        return 0

    if args.json:
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        return 0

    print(render_markdown(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


if __name__ == "__main__":
    sys.exit(_errors.run(main, sys.argv[1:]))
