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
import contextlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_sections import api_section
from appendix import APPENDIX_SPEC, TYPE_EMOJI, render_appendix
from factblocks import backup_existing, line_delta, refresh_blocks
from factblocks import mark_block as _gen
from ingest import factblocks
from lib import _config, _errors, _fsutil, _log, _mdutil, _source_state


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

ASPECTS = ('性能与规模', '并发与一致性', '扩展与兼容', '演化与版本')


PUBLIC_METHOD_LINE = re.compile(
    r'^\s*public\s+(?:static\s+|final\s+|synchronized\s+|native\s+|default\s+|abstract\s+)*'
    r'[\w<>\[\],.?\s]+\s+(\w+)\s*\(')


def _outline_path() -> str:
    """Where this book keeps its outline, resolved when used."""
    return _config.state_path('outline.json')


def _pkg_prefix() -> str:
    """The source package prefix this book declares."""
    return _config.SOURCES.get('package_prefix') or 'unknown'


def _generation() -> dict:
    """Generation limits from the policy, read when asked."""
    return _config.POLICY.get('generation', {})


def _templates() -> dict:
    """Prose templates, read when asked."""
    return _config.templates()


# Set by main(): whether the lead-in and summary may be written by the LLM.
# Facts, coordinates, tables and exercises never are - they come from the inventory.
_USE_LLM = False
PROSE_LIMIT = 220
PROSE_MIN_CHARS = 20


def prose_enabled() -> bool:
    """Whether prose generation is switched on for this run."""
    return bool(_USE_LLM or os.environ.get('BOOK_LLM_INGEST') == '1'
                or _config.llm_ingest_prose())


def prose(kind: str, fallback: str, enabled: bool | None = None, **facts) -> str:
    """One prose paragraph: deterministic by default, LLM-drafted on request.

    Only narrative sentences pass through here. The provider result is reduced
    to a single plain paragraph (no fences, headings or bullet marks) so it can
    never inject structure the gates rely on; any failure falls back to the
    deterministic text instead of breaking the ingest step.
    """
    if enabled is None:
        enabled = prose_enabled()
    if not enabled:
        return fallback
    try:
        # lazy: the offline path stays stdlib-only
        from lib import _llm, _llm_contract
        scenario = 'chapter-draft' if kind == 'lead' else 'summary'
        prompt = _prose_prompt(kind, facts)
        text = _llm.complete(prompt, scenario=scenario)
    except Exception as exc:
        print(f'  [warn] LLM prose unavailable ({exc}); using deterministic text',
              file=sys.stderr)
        return fallback
    body: list[str] = []
    in_fence = False
    for line in (text or '').splitlines():
        if line.strip().startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = line.strip(' #>*-\t')
        if stripped:
            body.append(stripped)
    cleaned = ' '.join(body).replace('`', '')[:PROSE_LIMIT]
    return _llm_contract.enforce(kind, prompt, cleaned, facts) or fallback


def _prose_prompt(kind: str, facts: dict) -> str:
    """Prompt for one prose paragraph; where it comes from is `lib._llm_prompts`."""
    from lib import _llm_prompts  # noqa: PLC0415 - keeps the offline path stdlib-only

    return _llm_prompts.render(kind, facts)


def tpl(key: str, fallback: str, **facts) -> str:
    """Render a config-provided string template; falls back to the default."""
    pattern = _templates().get(key)
    if not isinstance(pattern, str):
        pattern = fallback
    try:
        return pattern.format(**facts)
    except (KeyError, IndexError):
        return fallback.format(**facts)
MAX_TABLE_ROWS = int(_generation().get('max_api_rows', 20))


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Markdown table lines, capped for readability."""
    return _mdutil.table(headers, rows, MAX_TABLE_ROWS)


def _sections(cn: int, title: str, packages: dict, cross: tuple[str, str]) -> list[str]:
    """Render the body sections for one chapter number.

    The numbers every section quotes are computed once in `_chapter_context`;
    the body is then assembled section group by section group, so each helper
    reads the same facts the previous group printed instead of deriving them
    again.
    """
    pkgs_sorted = sorted(packages.items(), key=lambda kv: -kv[1]['lines'])
    total_lines = sum(p['lines'] for p in packages.values()) or 1
    cross_num, cross_name = cross
    ctx = _chapter_context(cn, packages, pkgs_sorted, total_lines)
    ctx['cross'] = cross
    out = _map_sections(cn, packages, ctx)
    out += _api_sections(cn, ctx)
    reading, cn_tradeoff = _reading_sections(cn, cross_num, cross_name, ctx)
    out += reading
    out += _tradeoff_sections(cn, ctx, cn_tradeoff)
    out += _deep_dive_sections(cn, ctx, cn_tradeoff)
    terms, cn_summary = _term_sections(cn, packages, ctx, cn_tradeoff)
    out += terms
    out += _summary_sections(cn, packages, ctx, cn_summary)
    out += _aspect_sections(cn, ctx, cn_summary)
    out += _checklist_sections(cn, packages, ctx, cn_summary)
    return out


def _chapter_context(cn: int, packages: dict, pkgs_sorted: list[tuple[str, dict]],
                     total_lines: int) -> dict:
    """The facts every section of this chapter body quotes."""
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
             'take': int(_generation().get('max_classes_per_package', 4)),
             'others': max(0, len(packages) - 1),
             'files': top_info.get('files', 0), 'dep': dep_head}
    facts_intro = {'num': cn, 'pkgs': len(packages), 'lines': f'{total_lines:,}',
                   'sig': '、'.join(list(packages)[:3]) or '—',
                   'top': next(iter(packages), '—')}
    return {'cn': cn, 'pkgs_sorted': pkgs_sorted, 'total_lines': total_lines,
            'top_pkg': top_pkg, 'top_info': top_info,
            'second_pkg': second_pkg, 'second_info': second_info,
            'big': big, 'dep_head': dep_head,
            'facts': facts, 'facts_intro': facts_intro}


def _map_sections(cn: int, packages: dict, ctx: dict) -> list[str]:
    """§1 module map and §2 core types: what the chapter is made of."""
    facts = ctx['facts']
    facts_intro = ctx['facts_intro']
    pkgs_sorted = ctx['pkgs_sorted']
    L: list[str] = []
    L += [f'## {cn}.1 模块版图', '',
          tpl('map_intro', '本章覆盖 {pkgs} 个包、{lines} 行实现。',
              **facts_intro), '']
    keep = int(_generation().get('max_packages_per_table', 12))
    map_lines = _table(['包', '文件数', '行数', '职责'],
                       [[f'`{p}`', f"{i['files']}", f"{i['lines']:,}",
                         i['summary'] or '（无包注释，按主类型归纳）']
                        for p, i in pkgs_sorted[:keep]])
    if len(pkgs_sorted) > keep:
        rest = ', '.join(f'`{p}`' for p, _ in pkgs_sorted[keep:])
        map_lines += [f'其余 {len(pkgs_sorted) - keep} 个包规模较小：{rest}。', '']
    L += _gen('packages', map_lines)

    L += [f'## {cn}.2 核心类型', '',
          tpl('types_intro',
              '每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。',
              **facts), '']
    for idx, (pkg, info) in enumerate(pkgs_sorted, start=1):
        if not info['key_classes']:
            continue
        L += [f'### {cn}.2.{idx} `{pkg}`', '']
        L += _gen(f'types-{idx}', _table(
            ['类型', '行数', '公开方法', '职责'],
            [[f"`{c['name']}`", f"{c['lines']:,}", f"{c['public_methods']}",
              c['summary'] or '（无类注释，按方法名归纳）']
             for c in info['key_classes'][:int(_generation().get('max_classes_per_package', 4))]]))
    return L


def _api_sections(cn: int, ctx: dict) -> list[str]:
    """§3 entries and coordinates; the assembly lives in `ingest/api_sections`."""
    return api_section(cn, ctx, tpl=tpl, table=_table, mark=_gen, dep_count=info_dep_count)


def _reading_sections(cn: int, cross_num: str, cross_name: str,
                      ctx: dict) -> tuple[list[str], int]:
    """§4 reading path and §5 dependency direction; also picks the trade-off number.

    The trade-off heading number depends on whether a dependency table was
    printed, so it leaves here as the second return value.
    """
    facts = ctx['facts']
    top_pkg = ctx['top_pkg']
    big = ctx['big']
    dep_head = ctx['dep_head']
    pkgs_sorted = ctx['pkgs_sorted']
    L: list[str] = []
    # A chapter can map to no package at all (an empty or front-matter-only
    # outline); the reading path then falls back to the placeholders instead of
    # indexing an empty list.
    first_pkg = pkgs_sorted[0][0] if pkgs_sorted else top_pkg
    last_pkg = pkgs_sorted[-1][0] if pkgs_sorted else top_pkg
    last_lines = pkgs_sorted[-1][1].get('lines', 0) if pkgs_sorted else 0
    L += [f'## {cn}.4 阅读路径', '',
          tpl('path_intro', '从 `{top}` 先读骨架类，再沿依赖下钻。', **facts), '',
          (f'1. 先读 `{first_pkg}` 的 package-info 与 '
           f'`{big["name"]}`，建立第{cn}章的职责边界。'),
          (f'2. 再读 `{big["name"]}` 的 {big.get("public_methods", 0)} 个公开入口，'
           f'确认它对 `{dep_head}` 的调用方向与加锁方式。'),
          (f'3. 最后读 `{last_pkg}`（本章最小包，'
           f'{last_lines:,} 行）的实现，'
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
        L += [f'## {cn}.5 依赖方向', '']
        L += _gen('deps', [
            ('下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；'
             '重构时优先看右侧出现频次最高的包。'), '',
            *_table(['包', '依赖（前 4）'], dep_rows)])
        cn_tradeoff = 6
    else:
        cn_tradeoff = 5
    return L, cn_tradeoff


def _tradeoff_sections(cn: int, ctx: dict, cn_tradeoff: int) -> list[str]:
    """Design trade-offs and the misreading they invite."""
    top_pkg = ctx['top_pkg']
    top_info = ctx['top_info']
    second_pkg = ctx['second_pkg']
    second_info = ctx['second_info']
    big = ctx['big']
    dep_head = ctx['dep_head']
    L: list[str] = []
    L += [
        f'## {cn}.{cn_tradeoff} 设计权衡', '',
        (f'`{top_pkg}` 有 {top_info["files"]} 个文件、{top_info["lines"]:,} 行。'
         f'平均每文件 {top_info["lines"] // max(1, top_info["files"]):,} 行。'),
        '',
        (f'其中 `{big["name"]}` 独占 {big["lines"]:,} 行，'
         f'{big["public_methods"]} 个公开方法。规模集中，风险也集中。'),
        '',
        (f'它对外声明 {info_dep_count(top_info)} 个 `{_pkg_prefix()}` 依赖，'
         f'最重的是 `{dep_head}`。依赖越集中，越说明它是被复用的底座。'),
        '',
        (f'与 `{second_pkg}`（{second_info["lines"]:,} 行）的分工是本章最该记住的边界。'
         '前者偏实现，后者偏编排。合并会打散扩展点。'),
        '',
        f'## {cn}.{cn_tradeoff + 1} 常见误区', '',
        (f'- **误区**：把 `{top_pkg}` 的行数当作复杂度上限。\n'
         f'  **为什么**：`{big["name"]}` 之外还有 {max(0, top_info["files"] - 1)} 个文件，'
         '其中多为类型族与样板，行数与理解成本不是一回事。'),
        '',
        (f'- **误区**：只读 `{big["name"]}` 的签名就能判断它的用法。\n'
         '  **为什么**：真正的约束写在调用方的加锁顺序里，签名看不出先后。'),
        '',
        (f'- **误区**：`{top_pkg}` 与 `{second_pkg}` 可以互换。\n'
         f'  **为什么**：前者 {top_info["files"]} 个文件、后者 {second_info["files"]} 个，'
         '扩展点分布不同，替换会打散边界。'),
        '',
    ]
    return L


def _deep_dive_sections(cn: int, ctx: dict, cn_tradeoff: int) -> list[str]:
    """§N deep reading: the numbers a reader should carry into the chapter."""
    facts = ctx['facts']
    top_info = ctx['top_info']
    big = ctx['big']
    dep_head = ctx['dep_head']
    total_lines = ctx['total_lines']
    L: list[str] = []
    share = round(100 * top_info.get('lines', 0) / max(1, total_lines))
    L += [f'## {cn}.{cn_tradeoff + 2} 深读要点', '']
    deep_items = _templates().get('deep_dive')
    if not isinstance(deep_items, list):
        deep_items = ['- `{top}` 占本章 {share}% 的实现行数。',
                      f'- `{{top}}` 依赖 {{deps}} 个 `{_pkg_prefix()}` 包，`{{dep}}` 最频繁。',
                      '- `{big}` 有 {methods} 个公开方法，是本章主干。']
    for item in deep_items:
        deep = {'top': facts['top'], 'share': share,
                'deps': info_dep_count(top_info), 'dep': dep_head,
                'big': big['name'], 'methods': big.get('public_methods', 0)}
        line = str(item)
        with contextlib.suppress(KeyError, IndexError):
            line = line.format(**deep)   # a template naming a fact it was not given stays literal
        L += [line]
    L += ['']
    return L


def _term_sections(cn: int, packages: dict, ctx: dict,
                   cn_tradeoff: int) -> tuple[list[str], int]:
    """Terminology block; returns the number the summary heading uses.

    Chapters without a term hit skip the block, which shifts every following
    heading number by one, so the caller gets the number back.
    """
    L: list[str] = []
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
    return L, cn_summary


def _summary_sections(cn: int, packages: dict, ctx: dict, cn_summary: int) -> list[str]:
    """Knowledge block, chapter summary and exercise block."""
    top_pkg = ctx['top_pkg']
    total_lines = ctx['total_lines']
    pkgs_sorted = ctx['pkgs_sorted']
    L: list[str] = []
    L += knowledge_block(cn, pkgs_sorted)
    summary_line = prose('summary',
                         f'- 本章覆盖 {len(packages)} 个包、{total_lines:,} 行。',
                         pkgs=len(packages), lines=f'{total_lines:,}', top=top_pkg)
    L += [f'## {cn}.{cn_summary} 本章小结', '',
          summary_line,
          f'- 关键入口与源码坐标见 §{cn}.3。',
          '- 职责优先取自注释，注释缺失处需结合调用点归纳。', '']

    L += [f'## {cn}.{cn_summary + 1} 延伸思考', '']
    L += exercise_block(cn, pkgs_sorted)
    return L


def _aspect_sections(cn: int, ctx: dict, cn_summary: int) -> list[str]:
    """§N the per-chapter angle, plus the dependency detail behind it."""
    top_pkg = ctx['top_pkg']
    top_info = ctx['top_info']
    second_pkg = ctx['second_pkg']
    second_info = ctx['second_info']
    big = ctx['big']
    dep_head = ctx['dep_head']
    pkgs_sorted = ctx['pkgs_sorted']
    L: list[str] = []
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
        L += [f'## {cn}.{cn_summary + 2}.1 依赖明细', '']
        L += _gen('dep-detail', [
            '按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。', '',
            *_table(['来源包', '目标包', '次数'], dep_detail)])
    return L


def _checklist_sections(cn: int, packages: dict, ctx: dict,
                        cn_summary: int) -> list[str]:
    """The reading checklist, the cross-index and the further-reading line."""
    top_pkg = ctx['top_pkg']
    second_pkg = ctx['second_pkg']
    big = ctx['big']
    cross_num, cross_name = ctx['cross']
    L: list[str] = []
    checklist_items = int(_generation().get('checklist_items', 5))
    L += [f'## {cn}.{cn_summary + 2}.2 阅读检查清单', '',
          (f'本章给出 {checklist_items} 条自查项，逐条确认后再进入下一章。'), '',
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
    for index in range(int(_generation().get('exercises_per_chapter', 4))):
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
    out = [f'## {cn}.9 知识点清单', '']
    out += _gen('knowledge', [
        '下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。', '',
        *_table(['类型', '包', '行数', '公开方法', '职责'], rows)])
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
    out = [f'## {cn}.{nxt} 跨章索引', '']
    out += _gen('cross-index', [
        '本章引用但不展开的包，按下面这张表跳到主责章节阅读。', '',
        *_table(['包', '主责章节'], rows)])
    return out


def rewrite_allowed(path: str, text: str, force: bool) -> bool:
    """Whether a rendered skeleton may replace what is already on disk.

    A skeleton is reproducible; written prose is not. So an existing file is only
    rewritten when it already holds the same text, or when the caller forces it.
    """
    existing = _fsutil.read_text(path) if os.path.isfile(path) else ''
    return force or not existing or existing == text


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
            lead = prose('lead',
                         ('> **本章导读**：本章由源码清单汇总而成，覆盖 '
                          f'{len(packages)} 个包、{ch["source_lines"]:,} 行实现；'
                          '读完应能说清这些包的职责边界与关键协作。'),
                         pkgs=len(packages), lines=f'{ch["source_lines"]:,}',
                         title=title)
            if not lead.startswith('>'):
                lead = f'> **本章导读**：{lead.lstrip("- ")}'
            out += [lead, '',
                    '> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。', '']

        out += _sections(num, title, subset, cross)
    return '\n'.join(out)






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


_INVENTORY: dict = {}


LOG = _log.get_logger('ingest')


def _space(text: str) -> str:
    """Normalise CJK/Latin spacing in prose; tables and fences stay untouched."""
    out = []
    in_fence = False
    for line in text.split('\n'):
        if line.lstrip().startswith('```'):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or line.lstrip().startswith('#'):
            out.append(line)
            continue
        out.append(_mdutil.space_cjk_latin(line))
    return '\n'.join(out)


def _append_appendix(ch: dict, dry_run: bool) -> str:
    """Append the coordinate block to one appendix; returns its status."""
    num = APPENDIX_SPEC[ch['file']][0]
    path = _config.manuscript(ch['file'])
    existing = _fsutil.read_text(path) if os.path.isfile(path) else ''
    if f'## {num}.1 ' in existing:
        return 'skip'
    block = render_appendix(ch)
    if dry_run:
        print(f'--- appendix {ch["file"]} (+{len(block.splitlines())} lines)')
        return 'written'
    _fsutil.write_text(path, existing.rstrip('\n') + '\n\n' + _space(block))
    print(f'  appended {ch["file"]} (+{len(block.splitlines())} lines)')
    return 'written'


def _refresh_chapter(ch: dict, text: str, dry_run: bool) -> str:
    """Swap only the marked blocks; returns 'refresh' | 'unchanged' | 'skip'."""
    path = _config.manuscript(ch['file'])
    existing = _fsutil.read_text(path) if os.path.isfile(path) else ''
    result = refresh_blocks(existing, text) if existing else None
    if result is None:
        reason = '文件不存在' if not existing else '无标记块'
        print(f'  skipped {ch["file"]}（{reason}，先上 --force 生成带标记的骨架）')
        return 'skip'
    new_text, removed, added = result
    if dry_run:
        print(f'--- {ch["file"]}（事实块 -{removed}/+{added} 行）')
        return 'refresh'
    if new_text == existing:
        print(f'  unchanged {ch["file"]}（事实块已是最新）')
        return 'unchanged'
    _fsutil.write_text(path, new_text)
    print(f'  refreshed {ch["file"]}（事实块 -{removed}/+{added} 行）')
    return 'refresh'


def _emit_chapter(ch: dict, args, stamp: str) -> str:
    """Write, refresh or skip one chapter; returns its status.

    Without ``--force`` an existing chapter is never thrown away: when it carries
    the generated markers only those blocks are swapped (``refresh``), and when it
    carries none the file is left alone and the skip is reported. ``--force`` is
    the explicit "rewrite the whole chapter" path, and it backs the old file up.
    """
    text = _space(render_chapter(ch))
    path = _config.manuscript(ch['file'])
    if args.refresh_facts:
        return _refresh_chapter(ch, text, args.dry_run)
    existing = _fsutil.read_text(path) if os.path.isfile(path) else ''
    if existing and not args.force:
        result = refresh_blocks(existing, text)
        if result is None:
            print(f'  skipped {ch["file"]}（正文无标记块，事实无从插入；--force 可整篇重生成）')
            return 'skip'
        new_text, removed, added = result
        if new_text == existing:
            print(f'  unchanged {ch["file"]}（事实块与源码一致）')
            return 'unchanged'
        if args.dry_run:
            print(f'--- {ch["file"]}（事实块 -{removed}/+{added} 行）')
            return 'refresh'
        _fsutil.write_text(path, new_text)
        print(f'  refreshed {ch["file"]}（事实块 -{removed}/+{added} 行）')
        return 'refresh'
    if args.dry_run:
        print(f'--- {ch["file"]} ({len(text.splitlines())} lines)')
        return 'written'
    old = _fsutil.read_text(path) if os.path.isfile(path) else ''
    if args.force and old:
        removed, added = line_delta(old, text)
        backup = backup_existing(path, stamp)
        where = f' → {os.path.relpath(backup, _config.BOOK_ROOT)}' if backup else ''
        print(f'  覆盖 {ch["file"]}（-{removed}/+{added} 行，备份{where}）')
    _fsutil.write_text(path, text)
    print(f'  wrote {ch["file"]} ({len(text.splitlines())} lines)')
    return 'written'


def _source_change_line() -> str:
    """Whether, and how, the source inventory moved since the previous ingest."""
    return _source_state.change_line(
        _config.state_path('source-inventory.json'),
        _config.state_path('source-inventory.prev.json'))[0]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--only', help='single chapter file name')
    parser.add_argument('--dry-run', action='store_true', help='print instead of writing')
    parser.add_argument('--force', action='store_true',
                        help='overwrite chapter files that already carry written prose '
                             '(the previous file is backed up first)')
    parser.add_argument('--refresh-facts', action='store_true',
                        help='replace only the marked generated blocks; '
                             'files without markers are skipped and reported')
    parser.add_argument('--check-markers', action='store_true',
                        help='report, per chapter, which generated blocks are missing '
                             'and where they would go (writes nothing)')
    parser.add_argument('--insert-markers', action='store_true',
                        help='insert the missing blocks at the planned anchors; '
                             'without --apply it only prints the plan')
    parser.add_argument('--apply', action='store_true',
                        help='with --insert-markers: write the files (backup first)')
    parser.add_argument('--plan', action='store_true',
                        help='只报告 --llm 会写哪些章、大约花多少调用，不写文件')
    parser.add_argument('--llm', action='store_true',
                        help='let the LLM draft the lead-in and summary prose '
                             '(facts, tables and coordinates stay deterministic)')
    return parser


def _marker_mode(outline: dict, args) -> int:
    """Report or perform marker insertion; the policy lives in `factblocks`."""
    return factblocks.marker_mode(
        outline['chapters'], args, spec=CHAPTER_SPEC, skeleton_for=render_chapter,
        path_of=lambda name: os.path.join(_config.MANUSCRIPT_DIR, name))


def _load_state():
    """(inventory, outline) from the derived state, or None when unreadable."""
    global _INVENTORY
    try:
        inventory = json.loads(_fsutil.read_text(
            _config.state_path('source-inventory.json')))
        outline = json.loads(_fsutil.read_text(_outline_path()))
    except json.JSONDecodeError as exc:
        print(f'error: state files are not valid JSON: {exc}', file=sys.stderr)
        return None
    _INVENTORY = inventory
    return inventory, outline


def _emit_all(outline: dict, args, stamp: str) -> dict[str, int]:
    """Render or refresh every chapter the outline lists; returns the counters."""
    counters = {'written': 0, 'skipped': 0, 'refreshed': 0, 'unchanged': 0, 'unmarked': 0}
    for chapter in outline['chapters']:
        if args.only and chapter['file'] != args.only:
            continue
        if chapter['file'] in APPENDIX_SPEC:
            counters['written'] += _append_appendix(chapter, args.dry_run) == 'written'
            continue
        if chapter['file'] not in CHAPTER_SPEC:
            continue
        status = _emit_chapter(chapter, args, stamp)
        counters['written'] += status == 'written'
        counters['refreshed'] += status == 'refresh'
        counters['unchanged'] += status == 'unchanged'
        counters['skipped'] += status == 'skip'
        counters['unmarked'] += status == 'skip' and args.refresh_facts
    return counters


def _report(counters: dict[str, int], args) -> None:
    if args.refresh_facts:
        print(f"刷新 {counters['refreshed']} 章 / 跳过 {counters['unmarked']} 章（无标记块）")
        return
    print(f"chapters written: {counters['written']}")
    if counters['refreshed']:
        print(f"事实块已刷新: {counters['refreshed']} 章（正文未动）")
    if counters['unchanged']:
        print(f"事实块无变化: {counters['unchanged']} 章")
    if counters['skipped']:
        print(f"chapters skipped: {counters['skipped']}"
              '（正文无标记块或需整篇重生成；--force 可重写）')
    if _USE_LLM and not counters['written']:
        print('LLM 未介入：本轮没有生成或重写的章节，导读/小结没有可润色的对象；'
              '要对已有正文润色请加 --force（旧文件先备份）或按章用 --only。')


# Two calls per chapter (lead-in, summary). The estimate is deliberately crude: it
# exists so an operator can decide before spending, not to bill anyone.
CALLS_PER_CHAPTER = 2
CHARS_PER_CALL = 1200


def _print_llm_plan(args) -> int:
    """What `--llm` would write, and roughly what it costs, without writing anything."""
    targets = list(CHAPTER_SPEC) + list(APPENDIX_SPEC)
    if args.only:
        targets = [name for name in targets if name == args.only]
    missing = [name for name in targets if not os.path.isfile(_config.manuscript(name))]
    planned = missing if not (args.force or args.only) else targets
    calls = len(planned) * CALLS_PER_CHAPTER
    print(f'计划：{"整篇重写" if args.force or args.only else "补缺"} {len(planned)} 章')
    print(f'  LLM 作用范围：每章的导读与小结点各一次调用（共 {calls} 次，'
          f'约 {calls * CHARS_PER_CALL // 1000}k 字符输入量级）；'
          '事实块、结构、代码摘录不走 LLM。')
    print(f'  本轮跳过：{len(targets) - len(planned)} 章（正文已在且未要求重写）')
    if not planned:
        print('  结论：没有需要 LLM 起草的内容，可以不加 --llm 直接构建。')
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.refresh_facts and args.force:
        print('error: --refresh-facts 与 --force 是两条路径，不能同时使用',
              file=sys.stderr)
        return 2

    global _USE_LLM
    _USE_LLM = bool(args.llm
                    or os.environ.get('BOOK_LLM_INGEST') == '1'
                    or _config.llm_ingest_prose())

    # Nothing to polish is knowable before the source scan, which is what makes the
    # wait long. Saying it up front costs milliseconds; saying it after two minutes
    # of scanning is how a run feels like it did nothing.
    if _USE_LLM and args.plan:
        return _print_llm_plan(args)
    if _USE_LLM and not (args.force or args.refresh_facts or args.only):
        targets = list(CHAPTER_SPEC) + list(APPENDIX_SPEC)
        missing = [name for name in targets if not os.path.isfile(_config.manuscript(name))]
        if not missing:
            print('本轮不会生成或重写任何章节：正文文件都在，没有需要润色的新正文。')
            print('LLM 不介入：导读/小结只在新生成或整篇重写的章节上润色。')
            print('要润色已有正文：加 --force（整篇重写，旧文件先备份），'
                  '或用 --only <章文件名> 只重写一章。')
            return 0
        # a first build is what the LLM is actually for: every chapter is new, so
        # every lead-in and summary is drafted, while facts and structure stay
        # deterministic -- say so before the scan, not after it
        print(f'本轮将生成 {len(missing)} 章；LLM 只为这些章的导读/小结起草文字，'
              '事实、结构、代码摘录仍由确定性流程生成。')

    state = _load_state()
    if state is None:
        return 2
    _inventory, outline = state

    if args.check_markers or args.insert_markers:
        return _marker_mode(outline, args)   # report or insert, never rewrite prose

    print(_source_change_line())
    counters = _emit_all(outline, args, time.strftime('%Y-%m-%d_%H%M%S'))
    _report(counters, args)
    return 0


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
