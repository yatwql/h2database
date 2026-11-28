#!/usr/bin/env python3
"""§3 of a chapter body: the API table, the type list, the per-class guide.

Split out of `ingest/chapters.py`, which was the largest module in the
toolchain: these sections are pure table/paragraph assembly over the package
inventory and depend on the renderer only through two callables it passes in.
"""
from __future__ import annotations

from collections.abc import Callable


def _api_rows(pkgs_sorted: list) -> list[list[str]]:
    """Entry -> source coordinates, the rows of the §3 table."""
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
    return rows


def _type_rows(pkgs_sorted: list) -> list[list[str]]:
    rows = []
    for pkg, info in pkgs_sorted:
        for cls in (info.get('key_classes') or [])[:5]:
            rows.append([f'`{cls["name"]}`', f'`{pkg}`',
                         f'{cls["lines"]:,}', f'{cls["public_methods"]}'])
    return rows


def _guide_entries(pkgs_sorted: list) -> list[tuple[str, dict]]:
    """(package, class) pairs the per-class guide walks through."""
    take = 8 if len(pkgs_sorted) <= 2 else 4
    return [(pkg, cls) for pkg, info in pkgs_sorted
            for cls in (info.get('key_classes') or [])[:take]]


def _coord_rows(pkgs_sorted: list) -> list[list[str]]:
    """Every entry that has a line number, for the coordinate appendix table."""
    rows = []
    for _pkg, info in pkgs_sorted:
        for cls in (info.get('key_classes') or [])[:6]:
            rel = cls.get('rel') or ''
            api_lines = cls.get('api_lines') or {}
            if not rel:
                continue
            for api in cls.get('api', [])[:6]:
                lineno = api_lines.get(api)
                if lineno:
                    rows.append([f'`{cls["name"]}.{api}()`', f'`{rel}:{lineno}`'])
    return rows


def api_section(cn: int, ctx: dict, *, tpl: Callable, table: Callable,
                mark: Callable, dep_count: Callable) -> list[str]:
    """§3 entries and coordinates: where to start reading, and in which file."""
    facts = ctx['facts']
    pkgs_sorted = ctx['pkgs_sorted']
    L: list[str] = []
    L += [f'## {cn}.3 关键 API 与源码坐标', '']
    rows = _api_rows(pkgs_sorted)
    L += mark('api', [
        tpl('api_intro',
            '下表把公开入口与源码位置对应起来，共 {rows} 条坐标。', **facts), '',
        *table(['入口', '源码坐标'], rows[:20] or [['`—`', '`org/example/...`']])])

    type_rows = _type_rows(pkgs_sorted)
    if type_rows:
        L += [f'## {cn}.3.1 公共类型清单', '']
        L += mark('type-list', [
            (f'本章抽样类型按包分组，共 {len(type_rows)} 行；'
             '规模与公开方法数是阅读优先级的第一信号。'), '',
            *table(['类型', '包', '行数', '公开方法'], type_rows)])

    guide = _guide_entries(pkgs_sorted)
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
                   f'读它之前先看包级依赖（{dep_count(info)} 个），'
                   '再决定是否顺带读同包的相邻类型。'),
                  '',
                  ]

    coord_rows = _coord_rows(pkgs_sorted)
    if coord_rows:
        L += [f'## {cn}.3.2 源码坐标明细', '']
        L += mark('coords', [
            (f'本章主责包中 {len(coord_rows)} 个公开入口的行号，'
             '按类聚簇，可直接跳转阅读。'), '',
            *table(['入口', '源码坐标'], coord_rows)])
    return L
