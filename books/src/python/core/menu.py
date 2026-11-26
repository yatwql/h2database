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

import time
from dataclasses import dataclass

from lib import _log, _perfhistory

BACK_KEY = "0"
BACK_ACTION = "@back"
QUIT_ACTION = "@quit"
OPEN_PREFIX = "@open:"
SETTINGS_SCREEN = "settings"
PROVIDERS_SCREEN = "providers"
BOOKS_SCREEN = "books"
BOOK_ACTION_PREFIX = "@book:"
NEW_BOOK_ACTION = "@new-book"

# Letter shortcut -> the row key it stands for, per screen. Matching is
# case-insensitive, so S and s both run "1 源码 → 手稿".
LETTER_ALIASES: dict[str, dict[str, str]] = {
    "main": {
        "a": "1",
        "l": "2",
        "m": "3",
        "e": "4",
        "p": "5",
        "f": "6",
        "b": "7",
        "c": "8",
        "t": "9",
        "q": "0",
    },
    "library": {"s": "1", "n": "2"},
}


def aliases(screen: str) -> dict[str, str]:
    """Letter shortcuts that apply to one screen."""
    return LETTER_ALIASES.get(screen, {})


def resolve(screen: str, key: str) -> str:
    """Map a pressed key onto the row key it means (letters are case-insensitive)."""
    lowered = key.lower()
    return aliases(screen).get(lowered, lowered)


def display_key(screen: str, key: str) -> str:
    """How a row's key is rendered: ``1/s`` when a letter shortcut exists."""
    letters = [letter for letter, target in aliases(screen).items() if target == key]
    return f"{key}/{letters[0].upper()}" if letters else key


# screen -> [(key, action, label)]; `@open:<screen>` and `@back` are navigation
SCREENS: dict[str, list[tuple[str, str, str]]] = {
    "main": [
        ("1", "analyze", "源码 → 手稿"),
        ("2", "analyze-llm", "源码 → 手稿（LLM 润色导读/小结）"),
        ("3", "build", "手稿 → Markdown + HTML"),
        ("4", "deliver", "EPUB + PDF（按需）"),
        ("5", "print", "印刷版 PDF（按需）"),
        ("6", "deliver-all", "手稿 → Markdown + HTML + EPUB + 全版 PDF"),
        ("7", OPEN_PREFIX + "library", "书籍管理：切换 / 新增"),
        ("8", OPEN_PREFIX + "config", "配置：状态、配置项与 LLM"),
        ("9", OPEN_PREFIX + "quality", "质量：门禁与测试"),
        (BACK_KEY, QUIT_ACTION, "退出"),
    ],
    "library": [
        ("1", OPEN_PREFIX + BOOKS_SCREEN, "切换书籍"),
        ("2", NEW_BOOK_ACTION, "新增书籍"),
        (BACK_KEY, BACK_ACTION, "返回主菜单"),
    ],
    "quality": [
        ("1", "check", "全部质量门禁"),
        ("2", "test", "测试套件（快档）"),
        (BACK_KEY, BACK_ACTION, "返回主菜单"),
    ],
    "config": [
        ("1", "status", "书籍 / 配置 / LLM 状态"),
        ("2", "llm-ask", "用配置的 provider 提问"),
        ("3", OPEN_PREFIX + SETTINGS_SCREEN, "修改配置项（书名、目录、日志级别…）"),
        ("4", OPEN_PREFIX + PROVIDERS_SCREEN, "LLM provider 优先级"),
        ("5", "doctor", "依赖与环境"),
        ("6", "analyze-refresh", "刷新事实块（只改可重算的表，正文不动）"),
        (BACK_KEY, BACK_ACTION, "返回主菜单"),
    ],
}

# The main screen reads as three groups: what turns source into a book, what
# manages books, and what configures the toolchain. Group order is reading
# order; rows keep the order they have in SCREENS. Rows not named here (退出)
# render after the last group, so the exit key never sits inside a group.
MENU_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("源码成书", ("1", "2", "3", "4", "5", "6")),
    ("书籍管理", ("7",)),
    ("配置与管理", ("8", "9")),
]


def groups_for(screen: str) -> list[tuple[str, tuple[str, ...]]]:
    """Group headings and their row keys for one screen (empty = ungrouped)."""
    return MENU_GROUPS if screen == "main" else []


# screens whose rows come from live data instead of SCREENS
DYNAMIC_SCREENS = (SETTINGS_SCREEN, PROVIDERS_SCREEN, BOOKS_SCREEN)

PARENT: dict[str, str] = dict.fromkeys(("quality", "config", "library"), "main")
PARENT.update({SETTINGS_SCREEN: "config", PROVIDERS_SCREEN: "config", BOOKS_SCREEN: "library"})

TITLES: dict[str, str] = {
    "main": "主菜单",
    "quality": "质量",
    "config": "配置与状态",
    "library": "书籍管理",
    "books": "书籍",
    SETTINGS_SCREEN: "配置项",
    PROVIDERS_SCREEN: "LLM provider 优先级",
}

# Entries whose output depends on the provider.
LLM_ACTIONS = frozenset({"analyze-llm", "llm-ask"})

# Actions that rewrite many artifacts and take minutes.
CONFIRM_ACTIONS = frozenset({"deliver", "deliver-all", "print"})

# What each action rewrites, in the words the prompts use. The menu labels stay short;
# a confirmation and a progress line have to say exactly which artifacts are about to
# be replaced, otherwise "重建产物" leaves the user guessing what will change.
ARTIFACTS: dict[str, str] = {
    "analyze": "手稿（data/manuscript 的章节骨架）",
    "analyze-llm": "手稿（导读/小结的措辞）",
    "analyze-refresh": "手稿里的事实块（包表、类型表、源码坐标）",
    "build": "合并 Markdown 与 HTML（dist/<book>.md、dist/<book>.html）",
    "deliver": "EPUB 与标准版 PDF（dist/<book>.epub、dist/<book>.pdf）",
    "deliver-all": "Markdown、HTML、EPUB、标准版 PDF、印刷版 PDF（dist/ 下五份产物）",
    "print": "印刷版 PDF（dist/<book>-print.pdf）",
}


# The confirmation line is read at a glance before a multi-minute run; the progress
# line and the outcome carry the paths, so the question only names the shapes.
SHORT_ARTIFACTS: dict[str, str] = {
    "analyze": "手稿骨架",
    "analyze-llm": "手稿措辞",
    "analyze-refresh": "手稿事实块",
    "build": "Markdown 与 HTML",
    "deliver": "EPUB 与标准 PDF",
    "deliver-all": "5 份产物（MD / HTML / EPUB / 标准 PDF / 印刷 PDF）",
    "print": "印刷版 PDF",
}


def short_artifacts(action: str) -> str:
    """A one-glance name for what an action rewrites, for the confirmation line."""
    return SHORT_ARTIFACTS.get(action, artifacts(action))


def artifacts(action: str) -> str:
    """What an action rewrites, for confirmations and progress lines."""
    return ARTIFACTS.get(action, "")


# Order-of-magnitude durations, in seconds, for the actions that make the operator
# wait. They are a fallback: once the perf history has samples for the same mode, the
# estimate is narrowed to that median instead of a guess.
ESTIMATES: dict[str, tuple[int, int]] = {
    "analyze": (10, 120),
    "analyze-llm": (60, 300),
    "analyze-refresh": (2, 20),
    "build": (2, 15),
    "deliver": (60, 150),
    "deliver-all": (100, 240),
    # measured 43 s for the print edition on this book; the range leaves room for a
    # slower machine without pretending the render is instant
    "print": (30, 90),
    "check": (8, 40),
    "test": (30, 90),
    "status": (1, 5),
    "doctor": (1, 10),
    "llm-ask": (5, 60),
}

# which perf-history mode a shortcut's duration can be read from
_ESTIMATE_MODES = {"build": "build", "deliver": "deliver", "check": "check", "test": "test"}


def _mode_median(mode: str, window: int = 50) -> float:
    """Median total seconds recorded for one mode, 0 when there is no history.

    The file format lives in `lib._perfhistory`: `core` may only import `lib`, and the
    perf gate reads the same history through the same reader.
    """
    values = []
    for run in _perfhistory.history(window):
        if run.get("mode") != mode:
            continue
        try:
            seconds = float(run.get("seconds") or 0.0)
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            values.append(seconds)
    if not values:
        return 0.0
    values.sort()
    return values[len(values) // 2]


def estimate(action: str) -> tuple[int, int] | None:
    """Rough (low, high) seconds for an action, from history when it exists.

    A confirmation that says "this takes a few minutes" is not a plan; a range the
    operator can compare against the clock is.
    """
    default = ESTIMATES.get(action)
    mode = _ESTIMATE_MODES.get(action)
    if mode:
        median = _mode_median(mode)
        if median:
            return int(median * 0.7), int(median * 1.6)
    if action == "deliver-all":
        median = _mode_median("deliver")
        if median:
            low, high = ESTIMATES["print"]
            return int(median + low), int(median * 1.4 + high)
    return default


# Where the cursor starts on each screen: the everyday next step, not ingest.
DEFAULT_ENTRY_KEY = {"main": "3", "quality": "1", "config": "1"}

TAIL_LINES = 15


def entries(screen: str = "main") -> list[tuple[str, str, str]]:
    """Rows of a static screen (dynamic screens are rendered from data)."""
    return SCREENS.get(screen, [])


def parent_of(screen: str) -> str:
    """Screen that `0` returns to; the main screen has none."""
    return PARENT.get(screen, "main")


def default_cursor(screen: str = "main") -> int:
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
    return action[len(OPEN_PREFIX) :] if action.startswith(OPEN_PREFIX) else None


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
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    shown = lines[-limit:]
    prefix = f"…（前 {len(lines) - len(shown)} 行略）\n" if len(lines) > len(shown) else ""
    return prefix + "\n".join(shown)


def run_report(action: str, label: str, on_progress=None, **kwargs) -> Outcome:
    """Run one action and summarise it (timing, exit code, output size, tail)."""
    from core import actions  # resolved per call: channels patch this module

    started = time.perf_counter()
    if on_progress is not None:
        kwargs["on_progress"] = on_progress
    code, text = actions.run(action, **kwargs)
    elapsed = time.perf_counter() - started
    counted = len([line for line in (text or "").splitlines() if line.strip()])
    return Outcome(
        action=action,
        label=label,
        code=code,
        output_lines=counted,
        tail=tail_of(text),
        elapsed=elapsed,
    )


def log_location() -> str:
    """Where the full log lives, for the operator's next step."""
    return _log.log_dir()
