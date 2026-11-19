#!/usr/bin/env python3
"""Build a miniature but structurally complete book for integration tests.

The fixture mirrors the real layout (book.toml + manuscript/ + dist/) so the
delivery scripts can be exercised end-to-end without touching the real
manuscript.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)

BOOK_TOML = """[book]
title = "测试之书"
version = "0.1"
merged_name = "test-book"

[paths]
manuscript = "data/manuscript"
dist = "dist"
docs = "docs"
tools = "tools"

[chapters]
files = [
    "cover.md",
    "ch1-test.md",
    "ch2-test.md",
]
front_glob = "front/*.md"
back_glob = "back/*.md"

[chapters.titles]
"ch1-test.md" = ["示例总览"]
"ch2-test.md" = ["核心模块"]

[chapters.numbering]
"ch1-test.md" = [1]
"ch2-test.md" = [2]

[chapters.coverage]
"ch1-test.md" = [1]
"ch2-test.md" = [2]

[chapters.packages]
"ch1-test.md" = ["org.example"]
"ch2-test.md" = ["org.example.core"]

[thresholds]
caption_min_chars = 6
caption_max_chars = 40
caption_fail_at = 0
index_main_min = 2
index_sub_min = 1
index_see_also_min = 1
exercises_min = 2
max_style_warnings = 99
ascii_max_cols = 100
pdf_max_mb = 12
epub_max_mb = 10

[sections]
per_chapter = ["本章小结", "延伸思考"]

[sources]
root = "../h2/src/main"
"""

COVER_MD = """# 测试之书

> 版本 v0.1 · 2026-01-01 · 1,000 行

副标题：集成测试用样本。
"""

FRONT_MD = """# 阅读指南

本书用于测试。
"""

CHAPTER_1 = """# 第1章 测试章节

> **本章导读**: 这是一个测试章节。

## 1.1 小节

正文一段。详见第2章《第2章 测试章节》。

```text
+--------+
| 组件 A |
+--------+
```

**图 1-1: 展示组件 A 的连接方式**

正文引用 `MVStore.java:10` 与 `MVStore.bumpChunk()`。

## 1.9 本章小结

小结。

## 1.10 延伸思考

1. 练习一
   - 难度：⭐
   - 提示：看 §1.1

2. 练习二
   - 难度：⭐⭐
   - 提示：看 §1.1

## 1.11 延展阅读

- 参考
"""

CHAPTER_2 = """# 第2章 测试章节

## 2.1 小节

另一个章节。详见第1章《第1章 测试章节》。

**图 2-1: 对比两个组件的差异**

## 2.9 本章小结

小结。

## 2.10 延伸思考

1. 练习三
   - 难度：⭐
   - 提示：看 §2.1

2. 练习四
   - 难度：⭐⭐
   - 提示：看 §2.1

## 2.11 延展阅读

- 参考
"""

GLOSSARY_MD = """# 术语表

## A

- **ACID**: 事务特性。
  **章节**：第1章 §1.1
  **相关**：[[MVStore]]

## M

- **MVStore**: 存储引擎。
  **章节**：第2章 §2.1
  **相关**：[[ACID]]
"""

INDEX_MD = """# 索引

## A

- ACID —— §1.1
  - 与 MVStore 的关系 —— §2.1
  see also: MVStore

## M

- MVStore —— §2.1
"""

BASE_JSON = {
    "sources": {"src_main": "../h2/src/main", "pom_root": "../h2/pom.xml",
                "file_suffix": ".java", "package_prefix": "org.h2", "language": "java"},
    "baselines": {
        "ascii": "data/baselines/ascii-baseline.json",
        "source_symbol": "data/baselines/source-symbol-baseline.json",
    },
    "toolchain": {"coverage_fail_under": 0, "pdf_max_mb": 12,
                  "epub_max_mb": 10, "ascii_max_cols": 100,
                  "max_style_warnings": 99},
}

STYLE_JSON = {
    "captions": {
        "leading_verbs": ["展示", "对比", "拆解", "标注", "追踪", "说明"],
        "vague_trailing": ["过程", "示例", "架构", "图", "机制", "流程"],
        "presets": {
            "strict": {"min_chars": 8, "max_chars": 30, "fail_at": 0},
            "normal": {"min_chars": 6, "max_chars": 35, "fail_at": 30},
            "loose": {"min_chars": 4, "max_chars": 45, "fail_at": 80},
        },
    },
    "diagrams": {"markers": ["┌", "└", "├", "│", "▼", "▲", "→"]},
    "thresholds": {"exercises_min_per_chapter": 1, "exercises_min_total": 2,
                   "index_main_min": 2, "index_sub_min": 1,
                   "index_see_also_min": 1, "glossary_min_entries": 2,
                   "chapters_min_cross_refs": 1},
    "quality": {"max_duplicate_ratio": 100, "max_avg_sentence": 80,
                "max_long_lines": 200, "min_coords_per_chapter": 0,
                "min_chapter_lines": 1, "max_chapter_lines": 5000,
                "max_table_rows": 200, "min_terms_per_chapter": 0,
                "min_exercises_per_chapter": 0},
    "generation": {"max_packages_per_table": 12, "max_classes_per_package": 4,
                   "max_api_rows": 20, "exercises_per_chapter": 4,
                   "checklist_items": 5},
}

LLM_PROVIDER = {
    "providers": {"mock": {"kind": "mock"}},
    "default_provider": "mock",
    "routing": {"scenario": {"summary": "mock"}, "book": {}, "chapter": {}},
}

LLM_SETTINGS = {
    "defaults": {"temperature": 0.3, "max_tokens": 512, "timeout_s": 10, "retries": 0},
    "scenarios": {"summary": {"max_tokens": 256}},
    "books": {}, "chapters": {},
}

LANGUAGE_JSON = {
    "code": "zh",
    "sections": {"guide": "本章导读", "summary": "本章小结",
                 "exercises": "延伸思考", "further": "延展阅读"},
    "exercise": {"hint_prefix": "提示", "review_prefix": "回顾"},
    "terms": {"reference_line": "术语参考", "glossary_title": "术语表",
              "glossary_link": "back/glossary.md"},
    "style": {"sentence_endings": "。！？；", "fullwidth_punctuation": True},
}

CASE_STUDIES_TOML = """
[scenarios.select]
[[scenarios.select.steps]]
component = "入口"
anchor = "§1.1"
decision = "从入口进入示例模块"

[scenarios.commit]
[[scenarios.commit.steps]]
component = "写入"
anchor = "§2.1"
decision = "提交路径的选择"

[scenarios.recover]
[[scenarios.recover.steps]]
component = "恢复"
anchor = "§2.1"
decision = "崩溃后的恢复点"
"""

CONFIG_JSON = {
    "thresholds": {
        "ascii_max_cols": 100,
        "pdf_max_mb": 12,
        "epub_max_mb": 10,
        "max_style_warnings": 99,
        "coverage_fail_under": 0,
        "exercises_min_per_chapter": 1,
        "exercises_min_total": 2,
        "index_main_min": 2,
        "index_sub_min": 1,
        "index_see_also_min": 1,
        "glossary_min_entries": 2,
        "chapters_min_cross_refs": 1,
    },
    "captions": {
        "leading_verbs": ["展示", "对比", "拆解", "标注", "追踪", "说明"],
        "vague_trailing": ["过程", "示例", "架构", "图", "机制", "流程"],
        "presets": {
            "strict": {"min_chars": 8, "max_chars": 30, "fail_at": 0},
            "normal": {"min_chars": 6, "max_chars": 35, "fail_at": 30},
            "loose": {"min_chars": 4, "max_chars": 45, "fail_at": 80},
        },
    },
    "diagrams": {"markers": ["┌", "└", "├", "│", "▼", "▲", "→"]},
    "sources": {"src_main": "../h2/src/main", "pom_root": "../h2/pom.xml"},
    "baselines": {
        "ascii": "data/baselines/ascii-baseline.json",
        "source_symbol": "data/baselines/source-symbol-baseline.json",
    },
}

FILES = {
    'data/manuscript/cover.md': COVER_MD,
    'data/manuscript/front/reading-guide.md': FRONT_MD,
    'data/manuscript/ch1-test.md': CHAPTER_1,
    'data/manuscript/ch2-test.md': CHAPTER_2,
    'data/manuscript/back/glossary.md': GLOSSARY_MD,
    'data/manuscript/back/index.md': INDEX_MD,
}


SUBDIRS = ('', 'lib', 'audit', 'manuscript', 'render', 'ingest', 'app')


def resolve_script(script: str) -> str:
    """Locate a delivery script by basename under books/src/python."""
    for sub in SUBDIRS:
        candidate = os.path.join(TOOLS_DIR, sub, script)
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(f'script not found: {script}')



def refresh_config(root: str) -> None:
    """Point lib._config at ``root`` and drop every cached config module."""
    os.environ['BOOK_ROOT'] = root
    for key in ('_config', 'lib._config', 'lib._log', '_log',
                'app', 'app.actions', 'app.settings', 'app.cli', 'app.tui'):
        sys.modules.pop(key, None)
    lib = sys.modules.get('lib')
    if lib is not None:
        for attribute in ('_config', '_log'):
            if hasattr(lib, attribute):
                delattr(lib, attribute)

def build_book(root: str, *, extra: dict[str, str] | None = None) -> str:
    """Materialise the fixture book under ``root`` and return the root path."""
    os.makedirs(os.path.join(root, 'dist'), exist_ok=True)
    os.makedirs(os.path.join(root, 'docs', 'managements'), exist_ok=True)
    os.makedirs(os.path.join(root, 'tools'), exist_ok=True)
    config_dir = os.path.join(root, 'data', 'tmpl')
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, 'book.toml'), 'w', encoding='utf-8') as fh:
        fh.write(BOOK_TOML)
    policy_dir = os.path.join(root, 'data', 'config')
    os.makedirs(policy_dir, exist_ok=True)
    for name, payload in (('base.json', BASE_JSON), ('style.json', STYLE_JSON)):
        with open(os.path.join(policy_dir, name), 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    for name, payload in (('llm_provider.json', LLM_PROVIDER),
                          ('llm_settings.json', LLM_SETTINGS)):
        with open(os.path.join(policy_dir, name), 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    language_dir = os.path.join(root, 'data', 'language')
    os.makedirs(language_dir, exist_ok=True)
    with open(os.path.join(language_dir, 'zh.json'), 'w', encoding='utf-8') as fh:
        json.dump(LANGUAGE_JSON, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(config_dir, 'case-studies.toml'), 'w', encoding='utf-8') as fh:
        fh.write(CASE_STUDIES_TOML)
    for rel, text in {**FILES, **(extra or {})}.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
    return root


def run(root: str, script: str, *args: str) -> subprocess.CompletedProcess:
    """Run a delivery script against the fixture book."""
    env = {**os.environ, 'BOOK_ROOT': root}
    return subprocess.run(
        [sys.executable, resolve_script(script), *args],
        capture_output=True, text=True, env=env, cwd=root, check=False,
    )


def run_inproc(root: str, script: str, *args: str) -> tuple[int, str]:
    """Run a delivery script in this process (coverage-friendly).

    Returns ``(exit_code, captured_output)``. Module-level path constants are
    re-read by clearing ``_config`` from ``sys.modules`` first.
    """
    import contextlib
    import io
    import runpy

    if TOOLS_DIR not in sys.path:
        sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

    previous_root = os.environ.get('BOOK_ROOT')
    previous_argv = sys.argv[:]
    refresh_config(root)
    sys.argv = [script, *args]
    buffer = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            runpy.run_path(resolve_script(script), run_name='__main__')
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.argv = previous_argv
        if previous_root is None:
            os.environ.pop('BOOK_ROOT', None)
        else:
            os.environ['BOOK_ROOT'] = previous_root
        for key in ('_config', 'lib._config', 'lib._log', '_log',
                'app', 'app.actions', 'app.settings', 'app.cli', 'app.tui'):
            sys.modules.pop(key, None)
        lib_mod = sys.modules.get('lib')
        if lib_mod is not None and hasattr(lib_mod, '_config'):
            delattr(lib_mod, '_config')
    return code, buffer.getvalue()


def load_module(root: str, name: str):
    """Import (or re-import) a delivery module with BOOK_ROOT pointed at root."""
    if TOOLS_DIR not in sys.path:
        sys.path.insert(0, TOOLS_DIR)
    previous_root = os.environ.get('BOOK_ROOT')
    refresh_config(root)
    try:
        sys.modules.pop(name, None)
        module_path = resolve_script(name + '.py')
        spec = importlib.util.spec_from_file_location(name, module_path)
        if spec is None or spec.loader is None:  # pragma: no cover - unreadable file
            raise ImportError(f'cannot load {name} from {module_path}')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if previous_root is None:
            os.environ.pop('BOOK_ROOT', None)
        else:
            os.environ['BOOK_ROOT'] = previous_root


def cleanup(root: str) -> None:
    shutil.rmtree(root, ignore_errors=True)
