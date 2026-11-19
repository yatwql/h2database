#!/usr/bin/env python3
"""Menu model and run reporting for the interactive channels.

The terminal UI renders what this module decides: which entries exist, which of
them spend LLM tokens, which need confirmation, where the cursor starts, and
what a finished run reports back. Channels hold no such rules themselves.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

# group -> [(key, action, label)]
GROUPS: dict[str, list[tuple[str, str, str]]] = {
    '内容': [('1', 'analyze', '源码 → 手稿'),
             ('l', 'analyze-llm', '源码 → 手稿（LLM 润色导读/小结）'),
             ('2', 'build', '手稿 → Markdown + HTML'),
             ('3', 'deliver', 'PDF + EPUB（按需）')],
    '质量': [('4', 'check', '全部质量门禁'),
             ('5', 'test', '测试套件（快档）')],
    '配置与状态': [('6', 'status', '书籍 / 配置 / LLM 状态'),
                   ('7', 'llm-ask', '用配置的 provider 提问'),
                   ('8', 'settings', '查看与修改配置'),
                   ('9', 'doctor', '依赖与环境')],
}

ENTRIES: list[tuple[str, str, str]] = [entry for entries in GROUPS.values()
                                       for entry in entries]

# Entries whose output depends on the provider.
LLM_ACTIONS = frozenset({'analyze-llm', 'llm-ask'})

# Actions that rewrite many artifacts and take minutes.
CONFIRM_ACTIONS = frozenset({'deliver'})

# Where the cursor starts: the everyday next step, not the ingest pipeline.
DEFAULT_ENTRY_KEY = '2'

TAIL_LINES = 15


def default_cursor() -> int:
    """Index of the default entry (0 when the configured key is missing)."""
    for index, entry in enumerate(ENTRIES):
        if entry[0] == DEFAULT_ENTRY_KEY:
            return index
    return 0


def shortcut_map() -> dict[str, tuple[str, str]]:
    """key -> (action, label) for direct key dispatch."""
    return {key: (action, label) for key, action, label in ENTRIES}


def index_of(key: str) -> int:
    """Row index for a shortcut key, or -1 when it is not a menu entry."""
    for index, entry in enumerate(ENTRIES):
        if entry[0] == key:
            return index
    return -1


def needs_confirmation(action: str) -> bool:
    return action in CONFIRM_ACTIONS


def is_llm(action: str) -> bool:
    return action in LLM_ACTIONS


@dataclass(frozen=True)
class Outcome:
    """What a finished action reports back to the operator."""

    action: str
    label: str
    code: int
    output_lines: int
    tail: str
    elapsed: float

    @property
    def ok(self) -> bool:
        return self.code == 0


def tail_of(text: str, limit: int = TAIL_LINES) -> str:
    """Last ``limit`` non-empty lines, with a note when earlier lines were cut."""
    lines = [line for line in (text or '').splitlines() if line.strip()]
    if not lines:
        return ''
    shown = lines[-limit:]
    prefix = f'…（前 {len(lines) - len(shown)} 行略）\n' if len(lines) > len(shown) else ''
    return prefix + '\n'.join(shown)


def run_report(action: str, label: str, **kwargs) -> Outcome:
    """Run one action and summarise it (timing, exit code, output size, tail)."""
    from core import actions  # resolved per call: channels patch this module

    started = time.perf_counter()
    code, text = actions.run(action, **kwargs)
    elapsed = time.perf_counter() - started
    counted = len([line for line in (text or '').splitlines() if line.strip()])
    return Outcome(action=action, label=label, code=code,
                   output_lines=counted, tail=tail_of(text), elapsed=elapsed)


def log_location() -> str:
    """Where the full log lives, for the operator's next step."""
    return os.path.join('books', 'logs')
