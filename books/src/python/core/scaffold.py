#!/usr/bin/env python3
"""Scaffold a new book (or a translation) from the current one's structure.

Creates a directory containing the four document-side files with the right
division of responsibility:

  data/tmpl/book.toml          structure: identity, paths, chapter list, titles,
                     numbering, coverage, package mapping
  data/tmpl/templates.toml     prose: narrative templates (placeholders kept)
  data/language/<code>.json    labels: section names, exercise hints, term line
  data/config/style.json       rules: thresholds and vocabulary (starting point)
  data/config/base.json        infrastructure: source tree, logging, budgets

Usage:
  python core/scaffold.py ../my-book --title "My Book"
  python core/scaffold.py ../translation --lang en --title "My Book (EN)"
  python core/scaffold.py ../copy --from-manuscript   # also copy chapters
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

BOOK_TOML_TEMPLATE = '''[book]
title = "{title}"
version = "0.1"
merged_name = "{slug}"

[project]
display_title_en = "{title}"
display_title_zh = "{title}"
author = ""
email = ""
publisher = ""
description = ""
running_head = "{title}"
breadcrumb_root = "{title}"

[paths]
dist = "dist"
docs = "docs"
manuscript = "{manuscript}"
tools = "src/python"
cover_image = ""

[chapters]
files = ["cover.md", "ch1-overview.md"]
front_glob = "front/*.md"
back_glob = "back/*.md"

[chapters.titles]
"ch1-overview.md" = ["{title} Overview"]

[chapters.numbering]
"ch1-overview.md" = [1]

[chapters.coverage]
"ch1-overview.md" = [1]

[chapters.packages]
"ch1-overview.md" = []
'''

COVER_MD = '''# {title}

> 版本 v0.1 · {date} · 0 行

**作者：**
**联系邮箱：**
'''

CHAPTER_MD = '''# 第1章 {title} Overview

> **本章导读**：本章介绍……

## 1.1 模块版图

（分析后由 ingest/chapters.py 生成版图、坐标与阅读路径；此处可写导读。）

## 1.9 本章小结

## 1.10 延伸思考

## 1.11 延展阅读
'''


def _language_pack(code: str) -> dict:
    source = os.path.join(_config.BOOK_ROOT, 'data', 'language', 'zh.json')
    try:
        pack = json.loads(_fsutil.read_text(source))
    except json.JSONDecodeError as exc:
        raise SystemExit(f'error: invalid language pack {source}: {exc}') from exc
    pack['code'] = code
    return pack


def _rel(path: str) -> str:
    """Path of ``path`` relative to the book root (posix separators)."""
    return os.path.relpath(path, _config.BOOK_ROOT).replace(os.sep, '/')


MANUSCRIPT_REL = _rel(_config.MANUSCRIPT_DIR)
TMPL_REL = _rel(os.path.dirname(_config.CONFIG_PATH))
CONFIG_REL = _rel(os.path.dirname(_config.BASE_POLICY_PATH))
LANG_REL = _rel(_config.LANGUAGE_DIR)


def _base_config() -> dict:
    """Infrastructure config for the new book (paths, logging, budgets)."""
    source = os.path.join(_config.BOOK_ROOT, 'data', 'config', 'base.json')
    try:
        current = json.loads(_fsutil.read_text(source))
    except json.JSONDecodeError as exc:
        raise SystemExit(f'error: invalid base config {source}: {exc}') from exc
    current['sources'] = {'src_main': '', 'languages': ['java'],
                          'suffixes': {'java': '.java', 'python': '.py', 'rust': '.rs'},
                          'file_suffix': '.java', 'package_prefix': ''}
    current.setdefault('logging', {'level': 'INFO', 'dir': 'logs', 'retention_days': 14})
    return current


# Sentence-length anchors per script family. A translation needs its own numbers:
# what reads long in Chinese reads fine in English and vice versa.
PROSE_ANCHORS = {
    'cjk': {'avg_sentence_good': 28, 'avg_sentence_bad': 45,
            'long_sentence_ratio': 8, 'bullet_ratio': 15},
    'latin': {'avg_sentence_good': 18, 'avg_sentence_bad': 30,
              'long_sentence_ratio': 12, 'bullet_ratio': 18},
}
CJK_LANGS = ('zh', 'ja', 'ko')


def _script_family(lang: str) -> str:
    return 'cjk' if lang.split('-')[0].lower() in CJK_LANGS else 'latin'


def style_for(lang: str) -> dict:
    """A fresh style.json for the new book: same schema, no inherited vocabulary.

    Structure (sections, keys) comes from the current style.json so the schema
    gate keeps passing; everything book- or language-specific is reset:
    terminology, banned link text, phrase lists, per-book limits and the prose
    anchors for the target script family.
    """
    source = os.path.join(_config.BOOK_ROOT, 'data', 'config', 'style.json')
    try:
        style = json.loads(_fsutil.read_text(source))
    except json.JSONDecodeError as exc:
        raise SystemExit(f'error: invalid style config {source}: {exc}') from exc

    style['_note'] = f'style.json for a new book ({lang}); thresholds are a starting point'
    family = _script_family(lang)
    prose = style.setdefault('prose', {})
    prose.update(PROSE_ANCHORS[family])

    rules = style.setdefault('style_rules', {})
    rules['terminology'] = []          # book-specific synonyms: start empty
    rules['banned_link_text'] = []
    if family != 'cjk':
        # Phrase lists below were written for Chinese prose; an English book must
        # not inherit them or every caption would be flagged.
        for key in ('leading_verbs', 'vague_trailing'):
            if isinstance(style.get('captions'), dict):
                style['captions'][key] = []
    depth = style.setdefault('content_depth', {})
    depth['glossary_ignore'] = []
    for section in ('limits', 'thresholds'):
        if isinstance(style.get(section), dict):
            style[section] = {}
    return style


def scaffold(target: str, title: str, lang: str, copy_manuscript: bool) -> list[str]:
    """Create the four document-side files (and optionally the chapters)."""
    target = os.path.abspath(target)
    created: list[str] = []
    slug = os.path.basename(target.rstrip(os.sep)) or 'book'

    def write(rel: str, text: str) -> None:
        path = os.path.join(target, rel)
        _fsutil.ensure_dir(path)
        if os.path.exists(path):
            return
        _fsutil.write_text(path, text)
        created.append(rel)

    write(f'{TMPL_REL}/book.toml', BOOK_TOML_TEMPLATE.format(title=title, slug=slug,
                                                 manuscript=MANUSCRIPT_REL))
    write(f'{TMPL_REL}/templates.toml', _fsutil.read_text(
        os.path.join(_config.BOOK_ROOT, 'data', 'tmpl', 'templates.toml')))
    write(f'{LANG_REL}/{lang}.json',
          json.dumps(_language_pack(lang), ensure_ascii=False, indent=2) + '\n')
    write(f'{CONFIG_REL}/base.json', json.dumps(_base_config(), ensure_ascii=False, indent=2) + '\n')
    write(f'{CONFIG_REL}/style.json',
          json.dumps(style_for(lang), ensure_ascii=False, indent=2) + '\n')
    write(f'{MANUSCRIPT_REL}/cover.md',
          COVER_MD.format(title=title, date=__import__('datetime').date.today().isoformat()))
    write(f'{MANUSCRIPT_REL}/ch1-overview.md', CHAPTER_MD.format(title=title))
    write(f'{MANUSCRIPT_REL}/front/.keep', '')
    write(f'{MANUSCRIPT_REL}/back/glossary.md', '# 术语表\n\n## A\n')
    write(f'{MANUSCRIPT_REL}/back/index.md', '# 索引\n\n## A\n')

    if copy_manuscript:
        source_dir = _config.MANUSCRIPT_DIR
        try:
            names = sorted(os.listdir(source_dir))
        except OSError as exc:
            raise SystemExit(f'error: cannot list {source_dir}: {exc}') from exc
        for name in names:
            src = os.path.join(source_dir, name)
            dst = os.path.join(target, *MANUSCRIPT_REL.split('/'), name)
            if os.path.isfile(src) and not os.path.exists(dst):
                _fsutil.write_text(dst, _fsutil.read_text(src))
                created.append(f'{MANUSCRIPT_REL}/{name}')
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('target', help='directory for the new book')
    parser.add_argument('--title', default='New Book', help='book title')
    parser.add_argument('--lang', default='zh', help='language code for the pack')
    parser.add_argument('--from-manuscript', action='store_true',
                        help='also copy the current chapters as a starting point')
    args = parser.parse_args(argv)

    created = scaffold(args.target, args.title, args.lang, args.from_manuscript)
    if not created:
        print(f'{args.target}: nothing created (files already exist)')
        return 0
    print(f'created {len(created)} file(s) under {args.target}:')
    for name in created:
        print(f'  {name}')
    print('\nnext: point base.json [sources].src_main at your source tree, '
          'then run bookctl analyze')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
