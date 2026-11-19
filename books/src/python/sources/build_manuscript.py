#!/usr/bin/env python3
"""Generate chapter drafts from the source inventory (stage 1 -> manuscript).

Every chapter keeps its H1 title (so index, glossary and cross-references stay
valid) and is rebuilt from facts: package sizes, class roles taken from
javadoc, public API surface, and verified source coordinates.

Usage:
  python build_manuscript.py                 # regenerate every mapped chapter
  python build_manuscript.py --only ch3-packages.md
  python build_manuscript.py --dry-run       # print, do not write
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

OUTLINE = os.path.join(_config.BOOK_ROOT, 'data', 'state', 'outline.json')
SOURCE_ROOT = _config.source_tree('src_main')

CHAPTER_SPEC = {
    'ch1-2-architecture.md': [(1, 'H2 总体架构'), (2, '分层模块划分')],
    'ch3-packages.md': [(3, '包结构与模块职责')],
    'ch4-5-modules-processes.md': [(4, '模块边界与依赖治理'), (5, '进程内数据流')],
    'ch6-1-data-structures.md': [(6, '数据结构：值、行与页')],
    'ch6-2-storage-algorithms.md': [(7, '存储与压缩算法')],
    'ch6-3-query-algorithms.md': [(8, '索引与表达式求值')],
    'ch7-sql-execution.md': [(9, 'SQL 解析与执行')],
    'ch8-query-optimizer.md': [(10, '查询优化器')],
    'ch9-10-persistence-locking.md': [(11, '持久化'), (12, '并发控制')],
    'ch11-12-guide-summary.md': [(13, '二次开发指南'), (14, '全书总结')],
}

TYPE_EMOJI = ('🟢', '🔵', '🟠')
EXERCISE_BANK = (
    '用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。',
    '挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。',
    '如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？',
    '列举本章中两处用空间换时间的设计，并说明其收益与上限。',
    '找一个失败路径（异常或回滚），说明状态如何回退到一致。',
)


PUBLIC_METHOD_LINE = re.compile(
    r'^\s*public\s+(?:static\s+|final\s+|synchronized\s+|native\s+|default\s+|abstract\s+)*'
    r'[\w<>\[\],.?\s]+\s+(\w+)\s*\(')


def first_public_method_line(rel_file: str, method: str) -> int | None:
    """1-based line of the first ``public ... method(`` in a source file."""
    path = os.path.join(SOURCE_ROOT, rel_file)
    if not os.path.isfile(path):
        return None
    for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
        m = PUBLIC_METHOD_LINE.match(line)
        if m and m.group(1) == method:
            return lineno
    return None


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Markdown table lines, header + separator + rows."""
    out = ['| ' + ' | '.join(headers) + ' |',
           '| ' + ' | '.join('---' for _ in headers) + ' |']
    out += ['| ' + ' | '.join(str(c) for c in row) + ' |' for row in rows]
    return out


def _sections(cn: int, title: str, packages: dict, cross: tuple[str, str]) -> list[str]:
    """Render the body sections for one chapter number."""
    pkgs_sorted = sorted(packages.items(), key=lambda kv: -kv[1]['lines'])
    total_lines = sum(p['lines'] for p in packages.values()) or 1
    cross_num, cross_name = cross
    L: list[str] = []
    L += [f'## {cn}.1 模块版图', '',
          (f'本章覆盖 {len(packages)} 个包、{total_lines:,} 行实现。'
          '下表按规模排序，职责取自 `package-info.java` 首句。'), '']
    L += _table(['包', '文件数', '行数', '职责'],
                [[f'`{p}`', f"{i['files']}", f"{i['lines']:,}",
                  i['summary'] or '（无包注释，按主类型归纳）']
                 for p, i in pkgs_sorted[:12]]) + ['']
    if len(pkgs_sorted) > 12:
        rest = ', '.join(f'`{p}`' for p, _ in pkgs_sorted[12:])
        L += [f'其余 {len(pkgs_sorted) - 12} 个包规模较小：{rest}。', '']

    L += [f'## {cn}.2 核心类型', '',
          '每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。', '']
    for idx, (pkg, info) in enumerate(pkgs_sorted, start=1):
        if not info['key_classes']:
            continue
        L += [f'### {cn}.2.{idx} `{pkg}`', '']
        L += _table(['类型', '行数', '公开方法', '职责'],
                    [[f"`{c['name']}`", f"{c['lines']:,}", f"{c['public_methods']}",
                      c['summary'] or '（无类注释，按方法名归纳）']
                     for c in info['key_classes'][:4]]) + ['']

    L += [f'## {cn}.3 关键 API 与源码坐标', '',
          '下表把公开入口与当前源码位置对应起来，行号由脚本核验。', '']
    rows = []
    for pkg, info in pkgs_sorted:
        for cls in info['key_classes'][:3]:
            rel = f"{pkg.replace('.', '/')}/{cls['name']}.java"
            if not os.path.isfile(os.path.join(SOURCE_ROOT, rel)):
                continue
            for api in _api_sample(pkg, cls['name'])[:2]:
                lineno = first_public_method_line(rel, api)
                rows.append([f"`{cls['name']}.{api}()`",
                             f'`{rel}:{lineno}`' if lineno else f'`{rel}`'])
    L += _table(['入口', '源码坐标'], rows[:20] or [['`—`', '`org/h2/...`']]) + ['']

    L += [f'## {cn}.4 阅读路径', '',
          '1. 先读包注释与最大类型，建立职责边界。',
          '2. 再读公开入口，确认调用方向与加锁方式。',
          '3. 最后读内部实现与数据结构，关注容量、并发与失败路径。', '',
          f'跨章衔接请对照第{cross_num}章《{cross_name}》。', '']

    hit_terms = _glossary_hits(packages)
    if hit_terms:
        L += [f'## {cn}.5 术语对照', '',
              '本章出现的专业术语与书末术语表的对应关系：', '']
        L += [f'- **{t}**：详见[术语表](back/glossary.md)对应条目。' for t in hit_terms[:8]] + ['']
        cn_summary = 6
    else:
        cn_summary = 5

    L += [f'## {cn}.{cn_summary} 本章小结', '',
          f'- 本章覆盖 {len(packages)} 个包、{total_lines:,} 行。',
          f'- 关键入口与源码坐标见 §{cn}.3。',
          '- 职责优先取自注释，注释缺失处需结合调用点归纳。', '']

    L += [f'## {cn}.{cn_summary + 1} 延伸思考', '',
          '下列题目把"读到的结构"转化为可应用的判断力。', '']
    for i in range(4):
        emoji = TYPE_EMOJI[i % 3]
        stars = '★' * (i + 1)
        body = EXERCISE_BANK[(cn + i) % len(EXERCISE_BANK)]
        L += [f'**{i + 1}. {emoji}{stars} {body}**', '',
              f'> 提示：回到 §{cn}.1 的表格，按规模排序挑选目标包。',
              f'> 回顾：§{cn}.1 模块版图', '']

    L += [f'## {cn}.{cn_summary + 2} 延展阅读', '',
          (f'- 详见第{cross_num}章《{cross_name}》。'), '']
    return L


def render_chapter(ch: dict) -> str:
    name = ch['file']
    spec = CHAPTER_SPEC.get(name)
    if not spec:
        return ''
    packages = ch['packages']
    items = sorted(packages.items(), key=lambda kv: -kv[1]['lines'])
    out: list[str] = []
    for idx, (num, title) in enumerate(spec):
        # split packages across the chapter numbers in a combined file
        if len(spec) == 1:
            subset = dict(items)
        else:
            chunk = (len(items) + len(spec) - 1) // len(spec)
            subset = dict(items[idx * chunk:(idx + 1) * chunk]) or dict(items)
        nxt = spec[idx + 1][0] if idx + 1 < len(spec) else spec[0][0] + (1 if len(spec) == 1 else 0)
        cross = (str(nxt), title if nxt == num else _cross_title(spec, nxt))
        out += [f'# 第{num}章 {title}', '']
        if idx == 0:
            out += [('> **本章导读**：本章由源码清单汇总而成，覆盖 '
                    f'{len(packages)} 个包、{ch["source_lines"]:,} 行实现；'
                    '读完应能说清这些包的职责边界与关键协作。'), '',
                    '> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。', '']

        out += _sections(num, title, subset, cross)
    return '\n'.join(out)


def _cross_title(spec: list, num: int) -> str:
    for n, t in spec:
        if n == num:
            return t
    return spec[0][1]


def _glossary_hits(packages: dict) -> list[str]:
    """Glossary terms that occur in this chapter's package/class summaries."""
    global _GLOSSARY
    if _GLOSSARY is None:
        text = _fsutil.read_text(_config.glossary_path())
        _GLOSSARY = [t.strip() for t in re.findall(r'^- \*\*([^*]+)\*\*', text, re.MULTILINE)]
    blob = ' '.join(
        [info['summary'] or '' for info in packages.values()]
        + [c['summary'] or '' for info in packages.values() for c in info['key_classes']]
        + list(packages)
    ).lower()
    return [t for t in _GLOSSARY if t.lower() in blob]


_GLOSSARY: list[str] | None = None


def _api_sample(pkg: str, class_name: str) -> list[str]:
    inventory = _INVENTORY
    entry = inventory['packages'].get(pkg, {})
    for cls in entry.get('classes', []):
        if cls['name'] == class_name:
            return cls['api'][:4]
    return []


_INVENTORY: dict = {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--only', help='single chapter file name')
    parser.add_argument('--dry-run', action='store_true', help='print instead of writing')
    args = parser.parse_args(argv)

    global _INVENTORY
    try:
        _INVENTORY = json.loads(_fsutil.read_text(
            os.path.join(_config.BOOK_ROOT, 'data', 'state', 'source-inventory.json')))
        outline = json.loads(_fsutil.read_text(OUTLINE))
    except json.JSONDecodeError as exc:
        print(f'error: state files are not valid JSON: {exc}', file=sys.stderr)
        return 2

    written = 0
    for ch in outline['chapters']:
        if args.only and ch['file'] != args.only:
            continue
        if ch['file'] not in CHAPTER_SPEC:
            continue
        text = render_chapter(ch)
        if args.dry_run:
            print(f'--- {ch["file"]} ({len(text.splitlines())} lines)')
            continue
        _fsutil.write_text(_config.manuscript(ch['file']), text)
        written += 1
        print(f'  wrote {ch["file"]} ({len(text.splitlines())} lines)')
    print(f'chapters written: {written}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
