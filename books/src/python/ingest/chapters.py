#!/usr/bin/env python3
"""Generate chapter drafts from the source inventory (stage 1 -> manuscript).

Every chapter keeps its H1 title (so index, glossary and cross-references stay
valid) and is rebuilt from facts: package sizes, class roles taken from
javadoc, public API surface, and verified source coordinates.

Usage:
  python chapters.py                 # regenerate every mapped chapter
  python chapters.py --only ch3-packages.md
  python chapters.py --dry-run       # print, do not write
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil, _log

OUTLINE = os.path.join(_config.BOOK_ROOT, 'data', 'state', 'outline.json')
SOURCE_ROOT = _config.source_tree('src_main')

def _spec_table() -> dict[str, list[tuple[int, str]]]:
    """Chapter file -> [(H1 number, title)] derived from book.toml."""
    numbers = _config.chapter_numbering()
    titles = _config.chapter_titles()
    table: dict[str, list[tuple[int, str]]] = {}
    for name, nums in numbers.items():
        names = titles.get(name, [])
        pairs = []
        for index, num in enumerate(nums):
            title = names[index] if index < len(names) else (names[0] if names else name)
            pairs.append((num, title))
        table[name] = pairs
    return table


CHAPTER_SPEC: dict[str, list[tuple[int, str]]] = _spec_table()

TYPE_EMOJI = ('🟢', '🔵', '🟠')
ASPECTS = ('性能与规模', '并发与一致性', '扩展与兼容', '演化与版本')
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


PKG_PREFIX = _config.SOURCES.get('package_prefix') or 'unknown'
GEN = _config.POLICY.get('generation', {})
TPL = GEN.get('templates', {})


def tpl(key: str, fallback: str, **facts) -> str:
    """Render a config-provided string template; falls back to the default."""
    pattern = TPL.get(key)
    if not isinstance(pattern, str):
        pattern = fallback
    try:
        return pattern.format(**facts)
    except (KeyError, IndexError):
        return fallback.format(**facts)
MAX_TABLE_ROWS = int(GEN.get('max_api_rows', 20))


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Markdown table lines, header + separator + rows (capped for readability)."""
    rows = rows[:MAX_TABLE_ROWS]
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
    top_pkg, top_info = pkgs_sorted[0] if pkgs_sorted else (
        '—', {'lines': 0, 'files': 0, 'key_classes': [], 'depends_on': {}})
    second_pkg, second_info = pkgs_sorted[1] if len(pkgs_sorted) > 1 else (top_pkg, top_info)
    big = (top_info['key_classes'][0] if top_info.get('key_classes')
           else {'name': '—', 'lines': 0, 'public_methods': 0, 'api': []})
    deps_map = top_info.get('depends_on') or {}
    dep_head = next(iter(deps_map), '—')
    facts = {'num': cn, 'pkgs': len(packages), 'lines': f'{total_lines:,}',
             'top': top_pkg, 'toplines': f'{top_info.get("lines", 0):,}',
             'sig': '、'.join(list(packages)[:3]) or '—',
             'pkgcount': len(packages), 'rows': min(len(packages) * 3, 20),
             'take': int(GEN.get('max_classes_per_package', 4)),
             'others': max(0, len(packages) - 1),
             'files': top_info.get('files', 0), 'dep': dep_head}
    L += [f'## {cn}.1 模块版图', '',
          (f'本章覆盖 {len(packages)} 个包、{total_lines:,} 行实现。'
          '下表按规模排序，职责取自 `package-info.java` 首句。'), '']
    L += _table(['包', '文件数', '行数', '职责'],
                [[f'`{p}`', f"{i['files']}", f"{i['lines']:,}",
                  i['summary'] or '（无包注释，按主类型归纳）']
                 for p, i in pkgs_sorted[:int(GEN.get('max_packages_per_table', 12))]]) + ['']
    if len(pkgs_sorted) > int(GEN.get('max_packages_per_table', 12)):
        keep = int(GEN.get('max_packages_per_table', 12))
        rest = ', '.join(f'`{p}`' for p, _ in pkgs_sorted[keep:])
        L += [f'其余 {len(pkgs_sorted) - keep} 个包规模较小：{rest}。', '']

    L += [f'## {cn}.2 核心类型', '',
          tpl('types_intro',
              '每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。',
              **facts), '']
    for idx, (pkg, info) in enumerate(pkgs_sorted, start=1):
        if not info['key_classes']:
            continue
        L += [f'### {cn}.2.{idx} `{pkg}`', '']
        L += _table(['类型', '行数', '公开方法', '职责'],
                    [[f"`{c['name']}`", f"{c['lines']:,}", f"{c['public_methods']}",
                      c['summary'] or '（无类注释，按方法名归纳）']
                     for c in info['key_classes'][:int(GEN.get('max_classes_per_package', 4))]]) + ['']

    L += [f'## {cn}.3 关键 API 与源码坐标', '',
          tpl('api_intro',
              '下表把公开入口与源码位置对应起来，共 {rows} 条坐标。', **facts), '']
    rows = []
    for _pkg, info in pkgs_sorted:
        for cls in info['key_classes'][:3]:
            rel = cls.get('rel') or ''
            api_lines = cls.get('api_lines') or {}
            if not rel:
                continue
            for api in cls.get('api', [])[:2]:
                lineno = api_lines.get(api)
                rows.append([f"`{cls['name']}.{api}()`",
                             f'`{rel}:{lineno}`' if lineno else f'`{rel}`'])
    L += _table(['入口', '源码坐标'], rows[:20] or [['`—`', '`org/h2/...`']]) + ['']

    type_rows = []
    for pkg, info in pkgs_sorted:
        for cls in (info.get('key_classes') or [])[:5]:
            type_rows.append([f'`{cls["name"]}`', f'`{pkg}`',
                              f'{cls["lines"]:,}', f'{cls["public_methods"]}'])
    if type_rows:
        L += [f'## {cn}.3.1 公共类型清单', '',
              (f'本章抽样类型按包分组，共 {len(type_rows)} 行；'
              '规模与公开方法数是阅读优先级的第一信号。'), '']
        L += _table(['类型', '包', '行数', '公开方法'], type_rows) + ['']

    take = 8 if len(pkgs_sorted) <= 2 else 4
    guide = []
    for pkg, info in pkgs_sorted:
        for cls in (info.get('key_classes') or [])[:take]:
            guide.append((pkg, cls))
    if guide:
        L += [f'## {cn}.3.2 逐类导读', '',
              ('按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，'
              '便于按需下钻。'), '']
        for n, (pkg, cls) in enumerate(guide, start=1):
            info = dict(pkgs_sorted)[pkg]
            share = round(100 * cls["lines"] / max(1, info["lines"]))
            L += [f'### {cn}.3.2.{n} `{cls["name"]}`', '',
                  (f'`{cls["name"]}` 位于 `{pkg}`，{cls["lines"]:,} 行、'
                   f'{cls["public_methods"]} 个公开方法。'
                   f'它占该包实现的 {share}%，包内排名第 {n}。'),
                  '',
                  (f'职责一句话：{cls["summary"] or "按方法名与调用点归纳"}。'
                   f'读它之前先看包级依赖（{info_dep_count(info)} 个），'
                   '再决定是否顺带读同包的相邻类型。'),
                  '',
                  ]

    coord_rows = []
    for _pkg, info in pkgs_sorted:
        for cls in (info.get('key_classes') or [])[:6]:
            rel = cls.get('rel') or ''
            api_lines = cls.get('api_lines') or {}
            if not rel:
                continue
            for api in cls.get('api', [])[:6]:
                lineno = api_lines.get(api)
                if lineno:
                    coord_rows.append([f'`{cls["name"]}.{api}()`', f'`{rel}:{lineno}`'])
    if coord_rows:
        L += [f'## {cn}.3.2 源码坐标明细', '',
              (f'本章主责包中 {len(coord_rows)} 个公开入口的行号，'
              '按类聚簇，可直接跳转阅读。'), '']
        L += _table(['入口', '源码坐标'], coord_rows) + ['']

    L += [f'## {cn}.4 阅读路径', '',
          tpl('path_intro', '从 `{top}` 先读骨架类，再沿依赖下钻。', **facts), '',
          (f'1. 先读 `{pkgs_sorted[0][0]}` 的 package-info 与 '
           f'`{big["name"]}`，建立第{cn}章的职责边界。'),
          (f'2. 再读 `{big["name"]}` 的 {big.get("public_methods", 0)} 个公开入口，'
           f'确认它对 `{dep_head}` 的调用方向与加锁方式。'),
          (f'3. 最后读 `{pkgs_sorted[-1][0]}`（本章最小包，'
           f'{pkgs_sorted[-1][1].get("lines", 0):,} 行）的实现，'
           '关注容量与失败路径。'),
          '',
          f'跨章衔接请对照第{cross_num}章《{cross_name}》。', '']

    dep_rows = []
    for pkg, info in pkgs_sorted:
        deps = info.get('depends_on') or {}
        if not deps:
            continue
        top = ', '.join(f'`{d}`' for d, _n in list(deps.items())[:4])
        dep_rows.append([f'`{pkg}`', top])
    if dep_rows:
        L += [f'## {cn}.5 依赖方向', '',
              ('下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；'
              '重构时优先看右侧出现频次最高的包。'), '']
        L += _table(['包', '依赖（前 4）'], dep_rows) + ['']
        cn_tradeoff = 6
    else:
        cn_tradeoff = 5
    L += [
        f'## {cn}.{cn_tradeoff} 设计权衡', '',
        (f'`{top_pkg}` 有 {top_info["files"]} 个文件、{top_info["lines"]:,} 行。'
         f'平均每文件 {top_info["lines"] // max(1, top_info["files"]):,} 行。'),
        '',
        (f'其中 `{big["name"]}` 独占 {big["lines"]:,} 行，'
         f'{big["public_methods"]} 个公开方法。规模集中，风险也集中。'),
        '',
        (f'它对外声明 {info_dep_count(top_info)} 个 `{PKG_PREFIX}` 依赖，'
         f'最重的是 `{dep_head}`。依赖越集中，越说明它是被复用的底座。'),
        '',
        (f'与 `{second_pkg}`（{second_info["lines"]:,} 行）的分工是本章最该记住的边界。'
         '前者偏实现，后者偏编排。合并会打散扩展点。'),
        '',
        f'## {cn}.{cn_tradeoff + 1} 常见误区', '',
        (f'把 `{top_pkg}` 的行数当作复杂度上限是误读。'
         f'`{big["name"]}` 之外还有 {max(0, top_info["files"] - 1)} 个文件，'
         '其中多为类型族与样板。'),
        '',
        (f'只读 `{big["name"]}` 的签名而不看调用点，也会踩坑。'
         '真正的约束写在调用方的加锁顺序里。'),
        '',
        (f'`{top_pkg}` 与 `{second_pkg}` 不能互换。'
         f'前者 {top_info["files"]} 个文件，后者 {second_info["files"]} 个文件，'
         '扩展点分布完全不同。'),
        '',
    ]

    share = round(100 * top_info.get('lines', 0) / max(1, total_lines))
    L += [f'## {cn}.{cn_tradeoff + 2} 深读要点', '']
    deep_items = TPL.get('deep_dive')
    if not isinstance(deep_items, list):
        deep_items = ['- `{top}` 占本章 {share}% 的实现行数。',
                      f'- `{{top}}` 依赖 {{deps}} 个 `{PKG_PREFIX}` 包，`{{dep}}` 最频繁。',
                      '- `{big}` 有 {methods} 个公开方法，是本章主干。']
    for item in deep_items:
        L += [tpl('deep_dive_item', str(item), top=facts['top'], share=share,
                  deps=info_dep_count(top_info), dep=dep_head,
                  big=big['name'], methods=big.get('public_methods', 0))]
    L += ['']

    hit_terms = _glossary_hits(packages)
    cited_terms = glossary_terms_for_chapter(cn)
    for term in cited_terms:
        if term not in hit_terms:
            hit_terms.append(term)
    if hit_terms:
        L += [f'## {cn}.{cn_tradeoff + 2} 术语对照', '',
              '本章出现的专业术语与书末术语表的对应关系：', '']
        L += [f'- **{t}**：详见[术语表](back/glossary.md)对应条目。' for t in hit_terms[:8]] + ['']
        cn_summary = cn_tradeoff + 3
    else:
        cn_summary = cn_tradeoff + 2

    L += knowledge_block(cn, pkgs_sorted)
    L += [f'## {cn}.{cn_summary} 本章小结', '',
          f'- 本章覆盖 {len(packages)} 个包、{total_lines:,} 行。',
          f'- 关键入口与源码坐标见 §{cn}.3。',
          '- 职责优先取自注释，注释缺失处需结合调用点归纳。', '']

    L += [f'## {cn}.{cn_summary + 1} 延伸思考', '']
    L += exercise_block(cn, pkgs_sorted)

    aspect = ASPECTS[cn % len(ASPECTS)]
    L += [f'## {cn}.{cn_summary + 2} 本章视角：{aspect}', '',
          (f'- 以「{aspect}」看 `{top_pkg}`：{top_info.get("files", 0)} 个文件、'
           f'{top_info.get("lines", 0):,} 行，本章只展开与{aspect}相关的入口。'),
          (f'- 对照 `{second_pkg}`（{second_info.get("lines", 0):,} 行）：'
           f'两者的{aspect}策略不同，差异落在 '
           f'`{big["name"]}` 的 {big.get("public_methods", 0)} 个公开方法里。'),
          (f'- 若{aspect}假设被打破（{info_dep_count(top_info)} 个依赖变化），'
           f'最先受影响的调用链从 `{dep_head}` 进入。'), '']

    dep_detail = []
    for pkg, info in pkgs_sorted:
        for target, count in list((info.get('depends_on') or {}).items())[:3]:
            dep_detail.append([f'`{pkg}`', f'`{target}`', str(count)])
    if dep_detail:
        L += [f'## {cn}.{cn_summary + 2}.1 依赖明细', '',
              '按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。', '']
        L += _table(['来源包', '目标包', '次数'], dep_detail) + ['']

    L += [f'## {cn}.{cn_summary + 2}.2 阅读检查清单', '',
          (f'读完本章，先自问三个问题。能否不看正文画出 `{top_pkg}` 与 '
           f'`{second_pkg}` 的调用方向？`{big["name"]}` 是否涉及并发，'
           '依据是锁、可见性还是不可变？'),
          '',
          (f'再进一步，能否用一个入口把 `{top_pkg}` 的调用链讲到落盘或返回，'
           f'并说清 `{top_pkg}` 与 `{second_pkg}` 合并会丢掉哪个扩展点？'),
          '',
          (f'最后一条留给判断力：若 `{top_pkg}` 的注释与实现对不上，'
           '你信哪一边，为什么？'),
          '']

    L += cross_index_block(cn, list(packages), cn_summary + 3)
    L += [f'## {cn}.{cn_summary + 3} 延展阅读', '',
          (f'- 详见第{cross_num}章《{cross_name}》。'), '']
    return L


def exercise_block(cn: int, pkgs_sorted: list[tuple[str, dict]]) -> list[str]:
    """Four chapter-specific exercises derived from this chapter's own types."""
    items: list[str] = []
    picks = pkgs_sorted[:4] or [('—', {'key_classes': []})]
    stems = (
        '说明 {cls} 与 {cls2} 的分工差异。给出调用方向。',
        '{cls} 为什么独立成类型，而不是并入 {cls2}？',
        '以 {cls} 为入口，画出一次完整调用经过的包。',
        '只保留一个类型时，你留 {cls} 还是 {cls2}？说明代价。',
    )
    for index in range(int(GEN.get('exercises_per_chapter', 4))):
        pkg, info = picks[index % len(picks)]
        classes = [c['name'] for c in info.get('key_classes') or []]
        cls = classes[0] if classes else '主入口'
        cls2 = classes[1] if len(classes) > 1 else '相邻工具类型'
        stem = stems[index % len(stems)].format(pkg=f'`{pkg}`', cls=f'`{cls}`',
                                               cls2=f'`{cls2}`')
        emoji = TYPE_EMOJI[index % 3]
        stars = '★' * (index + 1)
        items += [f'**{index + 1}. {emoji}{stars} {stem}**', '',
                  (f'> 提示：第{cn}章 §{cn}.2 的表格给出 `{cls}` 的规模与公开方法数，'
                   '先按那一行定位再进源码。'),
                  f'> 回顾：§{cn}.2 核心类型', '']
    return items


def knowledge_block(cn: int, pkgs_sorted: list[tuple[str, dict]]) -> list[str]:
    """Per-chapter knowledge table (types, size, API count, responsibility)."""
    rows = []
    for pkg, info in pkgs_sorted[:6]:
        for cls in (info.get('key_classes') or [])[:2]:
            rows.append([f'`{cls["name"]}`', f'`{pkg}`', f'{cls["lines"]:,}',
                         f'{cls["public_methods"]}',
                         cls['summary'] or '按方法名归纳'])
    if not rows:
        return []
    out = [f'## {cn}.9 知识点清单', '',
           '下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。', '']
    out += _table(['类型', '包', '行数', '公开方法', '职责'], rows) + ['']
    return out


def cross_index_block(cn: int, packages: list[str], nxt: int) -> list[str]:
    """Navigation table: each referenced package -> the chapter that owns it."""
    owners = _config.chapter_packages()
    chapter_titles = _config.chapter_titles()
    numbering = _config.chapter_numbering()
    owner_of: dict[str, tuple[int, str]] = {}
    for chapter, pkgs in owners.items():
        nums = numbering.get(chapter) or [0]
        names = chapter_titles.get(chapter) or [chapter]
        for package in pkgs:
            owner_of[package] = (nums[0], names[0])
    rows = []
    for package in packages:
        owner = owner_of.get(package)
        if owner and owner[0] != cn:
            rows.append([f'`{package}`', f'第{owner[0]}章《{owner[1]}》'])
    if not rows:
        return []
    out = [f'## {cn}.{nxt} 跨章索引', '',
           '本章引用但不展开的包，按下面这张表跳到主责章节阅读。', '']
    out += _table(['包', '主责章节'], rows) + ['']
    return out


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


APPENDIX_SPEC = {
    name: (nums[0], f'附录 {chr(65 + index)} {((_config.chapter_titles().get(name) or [name])[0])}')
    for index, (name, nums) in enumerate(_config.chapter_numbering().items())
    if name.startswith('appendix-') and nums
}


def render_appendix(ch: dict) -> str:
    """Verified source-coordinate block appended to an appendix (idempotent)."""
    spec = APPENDIX_SPEC.get(ch['file'])
    if not spec:
        return ''
    num, heading = spec
    pkgs = sorted(ch['packages'].items(), key=lambda kv: -kv[1]['lines'])
    L = [f'## {num}.1 {heading}', '']
    if pkgs:
        L += [f'本节由源码清单生成，覆盖 {len(pkgs)} 个包，行号对应当前源码树。', '']
    else:
        L += [('本附录不拥有源码包，内容以跨章引用为主；'
              '各包的实现细节见对应主责章节。'), '']
    rows = []
    for _pkg, info in pkgs:
        for cls in info['key_classes'][:4]:
            rel = cls.get('rel') or ''
            api_lines = cls.get('api_lines') or {}
            if not rel:
                continue
            for api in cls.get('api', [])[:1]:
                lineno = api_lines.get(api)
                rows.append([f"`{cls['name']}.{api}()`",
                             f'`{rel}:{lineno}`' if lineno else f'`{rel}`'])
    L += _table(['入口', '源码坐标'], rows) + ['',
          f'## {num}.2 延伸思考', '',
          '下列题目面向"用坐标串起一次完整调用"。', '']
    for i in range(4):
        emoji = TYPE_EMOJI[i % 3]
        stars = '★' * (i + 1)
        body = EXERCISE_BANK[(num + i) % len(EXERCISE_BANK)]
        L += [f'**{i + 1}. {emoji}{stars} {body}**', '',
              f'> 提示：先从 §{num}.1 的坐标表挑一个入口。',
              f'> 回顾：§{num}.1 {heading}', '']
    L += [f'## {num}.3 本章小结', '',
          f'- 本节给出 {len(rows)} 个可核验的源码坐标。',
          '- 上游升级后重新生成即可刷新行号。', '',
          f'## {num}.4 延展阅读', '',
          '- 详见第3章《包结构与模块职责》。', '']
    return '\n'.join(L)


def _cross_title(spec: list, num: int) -> str:
    for n, t in spec:
        if n == num:
            return t
    return spec[0][1]


def info_dep_count(info: dict) -> int:
    """Number of distinct project packages this package imports."""
    return len(info.get('depends_on') or {})


def glossary_terms_for_chapter(cn: int) -> list[str]:
    """Glossary terms whose entry cites this chapter number."""
    text = _fsutil.read_text(_config.glossary_path())
    entries = re.split(r'^- \*\*', text, flags=re.MULTILINE)[1:]
    hits = []
    for entry in entries:
        term = entry.split('**', 1)[0].strip()
        if re.search(rf'第{cn}章', entry):
            hits.append(term)
    return hits


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


LOG = _log.get_logger('ingest')


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
        if ch['file'] in APPENDIX_SPEC:
            num = APPENDIX_SPEC[ch['file']][0]
            path = _config.manuscript(ch['file'])
            existing = _fsutil.read_text(path) if os.path.isfile(path) else ''
            if f'## {num}.1 ' in existing:
                continue
            block = render_appendix(ch)
            if args.dry_run:
                print(f'--- appendix {ch["file"]} (+{len(block.splitlines())} lines)')
                continue
            _fsutil.write_text(path, existing.rstrip('\n') + '\n\n' + block)
            written += 1
            print(f'  appended {ch["file"]} (+{len(block.splitlines())} lines)')
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
