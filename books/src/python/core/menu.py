#!/usr/bin/env python3
"""Menu model and run reporting for the interactive channels.

The terminal UI renders what this module decides: which screens exist, which
entries they hold, which of them spend LLM tokens, which need confirmation,
where the cursor starts, and what a finished run reports back. Channels hold no
such rules themselves.

Two levels, and one rule for both: `0` goes back. On the main screen "back"
means leaving the program, which is what the main screen's own label says.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os
import time
from dataclasses import dataclass

BACK_KEY = '0'
BACK_ACTION = '@back'
QUIT_ACTION = '@quit'
OPEN_PREFIX = '@open:'
SETTINGS_SCREEN = 'settings'
PROVIDERS_SCREEN = 'providers'

# screen -> [(key, action, label)]; `@open:<screen>` and `@back` are navigation
SCREENS: dict[str, list[tuple[str, str, str]]] = {
    'main': [('1', 'analyze', '源码 → 手稿'),
             ('l', 'analyze-llm', '源码 → 手稿（LLM 润色导读/小结）'),
             ('2', 'build', '手稿 → Markdown + HTML'),
             ('3', 'deliver', 'PDF + EPUB（按需）'),
             ('4', OPEN_PREFIX + 'quality', '质量：门禁与测试'),
             ('5', OPEN_PREFIX + 'config', '配置：状态、配置项与 LLM'),
             (BACK_KEY, QUIT_ACTION, '退出')],
    'quality': [('1', 'check', '全部质量门禁'),
                ('2', 'test', '测试套件（快档）'),
                (BACK_KEY, BACK_ACTION, '返回主菜单')],
    'config': [('1', 'status', '书籍 / 配置 / LLM 状态'),
               ('2', 'llm-ask', '用配置的 provider 提问'),
               ('3', OPEN_PREFIX + SETTINGS_SCREEN, '修改配置项（书名、目录、日志级别…）'),
               ('4', OPEN_PREFIX + PROVIDERS_SCREEN, 'LLM provider 优先级'),
               ('5', 'doctor', '依赖与环境'),
               ('6', 'analyze-refresh', '刷新事实块（只改可重算的表，正文不动）'),
               (BACK_KEY, BACK_ACTION, '返回主菜单')],
}

# screens whose rows come from live data instead of SCREENS
DYNAMIC_SCREENS = (SETTINGS_SCREEN, PROVIDERS_SCREEN)

PARENT: dict[str, str] = dict.fromkeys(('quality', 'config'), 'main')
PARENT.update({SETTINGS_SCREEN: 'config', PROVIDERS_SCREEN: 'config'})

TITLES: dict[str, str] = {
    'main': '主菜单',
    'quality': '质量',
    'config': '配置与状态',
    SETTINGS_SCREEN: '配置项',
    PROVIDERS_SCREEN: 'LLM provider 优先级',
}

# Entries whose output depends on the provider.
LLM_ACTIONS = frozenset({'analyze-llm', 'llm-ask'})

# Actions that rewrite many artifacts and take minutes.
CONFIRM_ACTIONS = frozenset({'deliver'})

# Where the cursor starts on each screen: the everyday next step, not ingest.
DEFAULT_ENTRY_KEY = {'main': '2', 'quality': '1', 'config': '1'}

TAIL_LINES = 15


def entries(screen: str = 'main') -> list[tuple[str, str, str]]:
    """Rows of a static screen (dynamic screens are rendered from data)."""
    return SCREENS.get(screen, [])


def parent_of(screen: str) -> str:
    """Screen that `0` returns to; the main screen has none."""
    return PARENT.get(screen, 'main')


def default_cursor(screen: str = 'main') -> int:
    """Index of the screen's default entry (0 when the key is missing)."""
    wanted = DEFAULT_ENTRY_KEY.get(screen)
    for index, entry in enumerate(entries(screen)):
        if entry[0] == wanted:
            return index
    return 0


def index_of(screen: str, key: str) -> int:
    """Row index for a shortcut key on one screen, or -1 when absent."""
    for index, entry in enumerate(entries(screen)):
        if entry[0] == key:
            return index
    return -1


def opens_screen(action: str) -> str | None:
    """Screen a navigation action leads to (None for back and quit)."""
    return action[len(OPEN_PREFIX):] if action.startswith(OPEN_PREFIX) else None


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
