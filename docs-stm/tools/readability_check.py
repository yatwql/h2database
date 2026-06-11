#!/usr/bin/env python3
"""Readability checks for H2 analysis docs.

Usage:
  python readability_check.py              # Default: fence/width checks
  python readability_check.py --figures    # Also run figure-specific checks
                                           # (box-drawing closure, caption quality)
"""
from pathlib import Path
import re
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DOCS_DIR = REPO_ROOT / 'docs-stm'

DOCS = [
    DOCS_DIR / 'ch1-2-architecture.md',
    DOCS_DIR / 'ch3-packages.md',
    DOCS_DIR / 'ch4-5-modules-processes.md',
    DOCS_DIR / 'ch6-1-data-structures.md',
    DOCS_DIR / 'ch6-2-storage-algorithms.md',
    DOCS_DIR / 'ch6-3-query-algorithms.md',
    DOCS_DIR / 'ch7-8-sql-optimizer.md',
    DOCS_DIR / 'ch9-10-persistence-locking.md',
    DOCS_DIR / 'ch11-12-guide-summary.md',
]
CAPTION_RE = re.compile(r'^\*\*图 \d+-\d+:')
CAPTION_FULL_RE = re.compile(r'^\*\*图 (\d+-\d+):(.+?)\*\*$')
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
    box_lines = [(i, l) for i, l in enumerate(block_lines) if any(c in l for c in DIAGRAM_MARKERS)]
    if not box_lines:
        return

    # Count each type of corner character
    counts = {c: 0 for c in '┌┐└┘├┤┬┴┼'}
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


# --- Main pass: fence, width, box closure ---
for path in DOCS:
    lines = path.read_text(encoding='utf-8').splitlines()
    in_fence = False
    fence_start = 0
    block_lines = []
    for idx, line in enumerate(lines, 1):
        if line.strip().startswith('```'):
            if not in_fence:
                in_fence = True
                fence_start = idx
                block_lines = []
            else:
                marker_lines = [l for l in block_lines if any(c in l for c in DIAGRAM_MARKERS)]
                if marker_lines:
                    max_width = max(len(l) for l in block_lines) if block_lines else 0
                    if max_width > 118:
                        warnings.append(f'{path}:{fence_start} diagram width {max_width} > 118')
                    if len(block_lines) > 80:
                        warnings.append(f'{path}:{fence_start} diagram/code block length {len(block_lines)} > 80')
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

    # Caption quality check (--figures flag)
    if RUN_FIGURE_CHECKS:
        check_caption_quality(path, lines)

# --- HTML check ---
html_path = DOCS_DIR / 'h2-source-code-analysis.html'
if html_path.exists():
    html = html_path.read_text(encoding='utf-8')
    body = re.sub(r'<pre[^>]*>.*?</pre>', '', html, flags=re.S)
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
        failures.append(f'{html_path}: {len(outside_lines)} diagram-like lines outside <pre>, blocks: {runs}')
    elif outside_lines:
        warnings.append(f'{html_path}: {len(outside_lines)} inline visual-aid lines use box chars outside <pre> (non-block, acceptable)')

# --- Report ---
print('READABILITY FAILURES:', len(failures))
for item in failures[:80]:
    print('FAIL:', item)
print('READABILITY WARNINGS:', len(warnings))
for item in warnings[:120]:
    print('WARN:', item)

raise SystemExit(1 if failures else 0)
