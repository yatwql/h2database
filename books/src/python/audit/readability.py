#!/usr/bin/env python3
"""Readability checks for H2 analysis docs.

Usage:
  python readability.py              # Default: fence/width checks
  python readability.py --figures    # Also run figure-specific checks
                                           # (box-drawing closure, caption quality)
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import json
import re
import sys
from pathlib import Path

from lib import _config, _errors, _mdutil

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
DOCS_DIR = Path(_config.BOOK_ROOT)
MS_DIR = Path(_config.MANUSCRIPT_DIR)
DIST_DIR = Path(_config.DIST_DIR)

DOCS = [Path(p) for p in _config.chapter_files(include_cover=False)]
CAPTION_RE = _mdutil.FIGURE_PREFIX_RE
CAPTION_FULL_RE = _mdutil.FIGURE_CAPTION_RE
DIAGRAM_MARKERS = set('┌┐└┘├┤│┬┴┼')
# Box-drawing corner pairs for closure checking
OPENING_CORNERS = {'┌': '┐', '└': '┘', '├': '┤', '┬': '┴'}
CLOSING_CORNERS = {'┐': '┌', '┘': '└', '┤': '├', '┴': '┬'}

RUN_FIGURE_CHECKS = '--figures' in sys.argv

failures = []
warnings = []

def check_box_closure(block_lines, fence_start, path):
    """Check box-drawing character completeness within a diagram block."""
    # Collect lines with box-drawing characters
    box_lines = [(i, line) for i, line in enumerate(block_lines)
                 if any(c in line for c in DIAGRAM_MARKERS)]
    if not box_lines:
        return

    # Count each type of corner character
    counts = dict.fromkeys('┌┐└┘├┤┬┴┼', 0)
    for _, line in box_lines:
        for c in line:
            if c in counts:
                counts[c] += 1

    # Check paired openings/closings
    # ┌ should be paired with ┐ (top corners)
    if counts['┌'] != counts['┐']:
        warnings.append(
            f'{path}:{fence_start} box-drawing closure: '
            f'┌ ({counts["┌"]}) != ┐ ({counts["┐"]})'
        )

    # └ should be paired with ┘ (bottom corners)
    if counts['└'] != counts['┘']:
        warnings.append(
            f'{path}:{fence_start} box-drawing closure: '
            f'└ ({counts["└"]}) != ┘ ({counts["┘"]})'
        )

    # ├ should be paired with ┤ (T-junctions)
    if counts['├'] != counts['┤']:
        warnings.append(
            f'{path}:{fence_start} box-drawing closure: '
            f'├ ({counts["├"]}) != ┤ ({counts["┤"]})'
        )

    # ┬ should be paired with ┴ (top/bottom T-junctions)
    if counts['┬'] != counts['┴']:
        warnings.append(
            f'{path}:{fence_start} box-drawing closure: '
            f'┬ ({counts["┬"]}) != ┴ ({counts["┴"]})'
        )

def check_caption_quality(path, lines):
    """Check figure caption quality — length and verb presence."""
    for idx, line in enumerate(lines, 1):
        m = CAPTION_FULL_RE.match(line.strip())
        if m:
            fig_id = m.group(1)
            caption = m.group(2).strip()

            # Check minimum length
            if len(caption) < 8:
                warnings.append(
                    f'{path}:{idx} caption too short ({len(caption)} chars): '
                    f'图 {fig_id}: {caption}'
                )

            # Check for verb-like content (Chinese action/process indicators)
            # Common verb/action indicators in technical captions
            verb_indicators = [
                '流程', '过程', '对比', '关系', '结构', '示意',
                '步骤', '策略', '决策', '机制', '变换', '转换',
                '映射', '传播', '分配', '释放', '获取', '创建',
                '合并', '分裂', '插入', '删除', '更新', '查找',
                '搜索', '排序', '比较', '计算', '构建', '解析',
                '生命周期', '状态', '时序', '调用', '依赖',
                '路径', '布局', '架构', '层次', '分类', '组成',
                '数据流', '检测', '统计', '替换', '迁移', '演进',
                '构造', '迭代', '设计', '选择', '匹配', '评估',
                '追踪', '监控', '恢复', '保护', '验证', '诊断',
            ]
            has_verb = any(v in caption for v in verb_indicators)
            if not has_verb:
                warnings.append(
                    f'{path}:{idx} caption may lack verb: '
                    f'图 {fig_id}: {caption[:60]}'
                )

def _scan_fences(path, lines) -> list[str]:
    """Fence balance, diagram width/length and caption-inside-fence for one file."""
    failures: list[str] = []
    in_fence = False
    fence_start = 0
    block_lines: list[str] = []
    for idx, line in enumerate(lines, 1):
        if line.strip().startswith('```'):
            if not in_fence:
                in_fence = True
                fence_start = idx
                block_lines = []
            else:
                marker_lines = [row for row in block_lines
                                if any(c in row for c in DIAGRAM_MARKERS)]
                if marker_lines:
                    max_width = max(len(row) for row in block_lines) if block_lines else 0
                    if max_width > 118:
                        warnings.append(f'{path}:{fence_start} diagram width {max_width} > 118')
                    if len(block_lines) > 80:
                        warnings.append(f'{path}:{fence_start} diagram/code block length '
                                        f'{len(block_lines)} > 80')
                    # Box-drawing closure check (always run)
                    check_box_closure(marker_lines, fence_start, path)
                in_fence = False
            continue
        if in_fence:
            if CAPTION_RE.match(line.strip()):
                failures.append(f'{path}:{idx} caption inside fence')
            block_lines.append(line)

    if in_fence:
        failures.append(f'{path}:{fence_start} unclosed fence')
    return failures


def _check_html() -> None:
    """Diagram-like lines that escaped their <pre> block in the rendered HTML."""
    html_path = Path(_config.merged_html())
    if not html_path.exists():
        return
    html = html_path.read_text(encoding='utf-8')
    body = re.sub(r'<pre[^>]*>.*?</pre>', '', html, flags=re.DOTALL)
    lines = body.splitlines()
    outside_lines = [line for line in lines if any(c in line for c in DIAGRAM_MARKERS)]
    runs = []
    streak = 0
    for line in lines:
        if any(c in line for c in DIAGRAM_MARKERS):
            streak += 1
        else:
            if streak >= 3:
                runs.append(streak)
            streak = 0
    if streak >= 3:
        runs.append(streak)
    if runs:
        failures.append(f'{html_path}: {len(outside_lines)} diagram-like lines outside '
                        f'<pre>, blocks: {runs}')
    elif outside_lines:
        warnings.append(f'{html_path}: {len(outside_lines)} inline visual-aid lines use box '
                        f'chars outside <pre> (non-block, acceptable)')


def _report(failures: list[str], warnings: list[str], as_json: bool) -> int:
    print('READABILITY FAILURES:', len(failures))
    for item in failures[:80]:
        print('FAIL:', item)
    print('READABILITY WARNINGS:', len(warnings))
    for item in warnings[:120]:
        print('WARN:', item)
    if as_json:
        print(json.dumps({'failures': failures, 'warnings': warnings}, ensure_ascii=False))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    """Run the readability pass and print the report."""
    args = list(argv) if argv else list(sys.argv[1:])
    as_json = '--json' in args
    for path in DOCS:
        lines = path.read_text(encoding='utf-8').splitlines()
        failures.extend(_scan_fences(path, lines))
        if RUN_FIGURE_CHECKS:
            check_caption_quality(path, lines)

    _check_html()
    return _report(failures, warnings, as_json)


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
