#!/usr/bin/env python3
"""Terminal UI: two menu levels, live configuration and a compact dashboard.

  python app/tui.py                # interactive
  python app/tui.py --once status  # one action, then exit (scriptable)

Keys: number = run action, 0/Esc = back (quit on the main screen), c = settings,
r = reload config, ? = help, q = quit. The screen tree lives in core.menu.
Colour is used only on a real terminal and can be disabled with NO_COLOR=1.
"""
from __future__ import annotations

import argparse
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import actions, menu, settings
from lib import _config, _fsutil

from app import keys

_fsutil.pin_stdout_utf8()

USE_COLOR = sys.stdout.isatty() and not os.environ.get('NO_COLOR')

# One palette, used everywhere: chrome is quiet, identity is bright, keys are
# the only saturated colour in the menu so the eye lands on what is actionable.
PALETTE = {
    'frame': '38;5;240',        # dim grey: borders and rules
    'label': '38;5;245',        # muted grey: field labels
    'value': '38;5;252',        # near-white: field values
    'product': '1;38;5;231',    # bold bright white: the software itself
    'product_accent': '1;38;5;45',   # bright cyan: product name
    'book': '1;38;5;222',       # bright warm yellow: the book being built
    'book_accent': '38;5;179',
    'group': '1;38;5;45',       # bright cyan: menu groups
    'key': '1;38;5;114',        # bright green: what you can press
    'ok': '38;5;114',
    'warn': '38;5;221',
    'error': '38;5;203',
    'hint': '38;5;244',
    'cursor': '1;38;5;231',      # the highlighted row
    'cursor_bar': '1;38;5;45',   # its leading marker
    'value_ok': '38;5;114',
    'llm_badge': '38;5;179',   # amber: this row spends LLM tokens
    'llm_key': '1;38;5;214',   # brighter amber: the LLM shortcut itself
}


def _width(text: str) -> int:
    """Display width: CJK and fullwidth characters take two columns."""
    return sum(2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
               for ch in text)


def _key(text: str, colour: str | None = None) -> str:
    """Render one shortcut as [key] so the pressable thing stands out."""
    return _c(f'[{text}]', colour or PALETTE['key'])


def _c(text: str, code: str) -> str:
    return f'\033[{code}m{text}\033[0m' if USE_COLOR else text


def header() -> str:
    """Identity on top, operational facts below, chrome kept quiet."""
    info = settings.summary()
    source = info['source_dir'] or '(未配置)'
    # (label, value) pairs: labels are muted, values near-white.
    facts = [
        ('源码', f"{source}  {_c('(' + info['source_version'] + ')', PALETTE['hint'])}"),
        ('手稿', info['manuscript']),
        ('产物', info['dist']),
        ('语言', '{}   {} {}   {} {}'.format(
            info['languages'], _c('日志', PALETTE['label']), info['log_level'],
            _c('LLM', PALETTE['label']), info['llm_provider'])),
        ('用量', f"{_c('LLM 今日', PALETTE['label'])} {info['llm_spend']}   "
                 f"{_c('行数余量', PALETTE['label'])} {info['volume_margin']}"),
    ]
    label_width = max(_width(label) for label, _value in facts) + 1

    title_left = _c(_config.app_name(), PALETTE['product_accent'])
    updated = _config.tool_updated()
    title_rest = (f" · {_config.app_name_zh()}  "
                  f"{_c('v' + info['tool_version'], PALETTE['hint'])}"
                  + (f"  {_c('更新 ' + updated, PALETTE['hint'])}" if updated else ''))
    product_plain = (f' {_config.app_name()} · {_config.app_name_zh()}  '
                     f'v{info["tool_version"]}'
                     + (f'  更新 {updated}' if updated else ''))
    book_date = _config.book_updated()
    book_plain = (f' 书籍 {info["title"]}  v{info["version"]}'
                  + (f'  更新 {book_date}' if book_date else ''))
    book_line = (f' {_c("书籍", PALETTE["label"])} '
                 f'{_c(info["title"], PALETTE["book"])}'
                 f'  {_c("v" + info["version"], PALETTE["hint"])}'
                 + (f'  {_c("更新 " + book_date, PALETTE["hint"])}' if book_date else ''))

    inner = max(_width(product_plain), _width(book_plain),
                max(_width(f' {label} {value}') for label, value in facts)) + 1

    def pad(plain: str, rendered: str) -> str:
        return f"{rendered}{' ' * (inner - _width(plain))}"

    def fact_line(label: str, value: str) -> str:
        gap = ' ' * (label_width - _width(label))
        plain = f' {label}{gap}{value}'
        rendered = f' {_c(label, PALETTE["label"])}{gap}{value}'
        return _c('│', PALETTE['frame']) + pad(plain, rendered) + _c('│', PALETTE['frame'])

    product_line = pad(product_plain, ' ' + title_left + title_rest)
    book_padded = pad(book_plain, book_line)
    rows = [
        _c('╭' + '─' * inner + '╮', PALETTE['frame']),
        product_line,
        book_padded,
        _c('├' + '─' * inner + '┤', PALETTE['frame']),
        *[fact_line(label, value) for label, value in facts],
        _c('╰' + '─' * inner + '╯', PALETTE['frame']),
    ]
    # product/book lines need their frame characters painted without colour bleed
    rows[1] = rows[1].replace('╭', '│', 0)
    rows[1] = _c('│', PALETTE['frame']) + rows[1] + _c('│', PALETTE['frame'])
    rows[2] = _c('│', PALETTE['frame']) + rows[2] + _c('│', PALETTE['frame'])
    return '\n'.join(rows)


def screen_rows(screen: str) -> list[tuple[str, str, str]]:
    """(key, action, label) rows for any screen; dynamic screens build theirs."""
    if screen == menu.SETTINGS_SCREEN:
        rows = [(str(index), '@set:' + row['key'], f"{row['key']} = {row['value']}")
                for index, row in enumerate(settings.list_settings(), start=1)]
        return rows + [(menu.BACK_KEY, menu.BACK_ACTION, '返回上一级')]
    if screen == menu.BOOKS_SCREEN:
        active = os.path.abspath(_config.current().root)
        rows = []
        for index, root in enumerate(_config.candidate_books(), start=1):
            try:
                cfg = _config.Config(root)
                name = f"{cfg.title or os.path.basename(root)}  {root}"
            except _config.ConfigError:
                name = root
            rows.append((str(index), menu.BOOK_ACTION_PREFIX + root,
                         ('● ' if root == active else '  ') + name))
        return rows + [(menu.BACK_KEY, menu.BACK_ACTION, '返回上一级')]
    if screen == menu.PROVIDERS_SCREEN:
        rows = [(str(index), '@move:' + item['name'],
                 f"{index}. {item['name']}  priority {item['priority']}")
                for index, item in enumerate(settings.provider_order(), start=1)]
        return rows + [(menu.BACK_KEY, menu.BACK_ACTION, '返回上一级')]
    return menu.entries(screen)


def menu_text(screen: str = 'main', cursor: int | None = None) -> str:
    """One screen; `cursor` highlights a row (↑/↓ moves it)."""
    lines: list[str] = []
    for index, (key, action, label) in enumerate(screen_rows(screen)):
        marker = '❯' if cursor == index else ' '
        label_style = PALETTE['cursor'] if cursor == index else PALETTE['value']
        llm_row = menu.is_llm(action)
        badge = f" {_c('LLM', PALETTE['llm_badge'])}" if llm_row else ''
        key_label = key.upper() if llm_row else key
        key_colour = PALETTE['llm_key'] if llm_row else None
        lines.append(f" {_c(marker, PALETTE['cursor_bar'])} "
                     f"{_key(key_label, key_colour)}  "
                     f"{_c(label, label_style)}{badge}")
    lines.append('')
    if screen == 'main':
        lines.append(f"   {_key('0')} 退出  {_key('q')} / {_key('Ctrl+C')} 退出")
    else:
        lines.append(f"   {_key('0')} 返回上一级  {_key('q')} / {_key('Ctrl+C')} 退出")
    lines.append(f"   {_key('↑/↓')} 选择 · {_key('Enter')} 执行 · 数字键直达 · "
                 f"{_key('?')} 帮助")
    return '\n'.join(lines)


def screen_title(screen: str) -> str:
    """Breadcrumb so the operator always knows which level they are on."""
    trail = [screen]
    while trail[0] != 'main':
        trail.insert(0, menu.parent_of(trail[0]))
    names = [menu.TITLES.get(name, name) for name in trail]
    return _c(' › '.join(names), PALETTE['group'])


def help_text() -> str:
    return ('两级菜单：主菜单选类目，类目里选动作。二级目录按 `0` 回到上一级，\n'
            '主菜单按 `0` 或 `q` 退出。`c` 直接进配置项，`r` 重新读取配置。\n'
            '非交互场景用 `--once <动作>`，例如 `--once status`。')


def configure(reader=input) -> str:
    """Interactive editor for the writable settings (returns a log line)."""
    lines = ['可修改项：']
    rows = settings.list_settings()
    for index, row in enumerate(rows, start=1):
        lines.append(f"  {index}) {row['key']:<14} {row['value']:<24} {row['description']}")
    print('\n'.join(lines))
    choice = (reader('选择要修改的序号（回车取消）: ') or '').strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(rows):
        return '未修改'
    key = rows[int(choice) - 1]['key']
    value = (reader(f"{key} 的新值（当前 {rows[int(choice) - 1]['value']}）: ") or '').strip()
    if not value:
        return '未修改'
    try:
        stored = settings.set_value(key, value)
    except (KeyError, ValueError) as exc:
        return f'修改失败：{exc}'
    return f'已更新 {key} = {stored}'




def confirm(question: str, reader=input) -> bool:
    """y/N prompt for actions worth a second look."""
    answer = (reader(f'{question} [y/N] ') or '').strip().lower()
    return answer in ('y', 'yes', '是')


def run_entry(action: str, label: str, force: bool = False) -> str:
    """Run one action and render the outcome core.menu reports."""
    if action == 'settings':
        return configure()
    if menu.needs_confirmation(action) and not confirm(f'{label} 会重建全部产物，继续？'):
        return _c('已取消', PALETTE['hint'])
    sys.stdout.write(_c(f'⠿ 正在执行 {label}（{action}）…', PALETTE['hint']) + '\n')
    sys.stdout.flush()
    outcome = menu.run_report(action, label, force=force)
    verdict = (_c('✓ 完成', PALETTE['value_ok']) if outcome.ok
               else _c('✗ 失败', PALETTE['error']))
    mode = '  --force' if force else ''
    summary = (f'{verdict}  {outcome.label}{mode}  用时 {outcome.elapsed:.1f}s  '
               f'退出码 {outcome.code}  输出 {outcome.output_lines} 行')
    return (f'\n{outcome.tail}\n{summary}\n'
            f'{_c("详情见 " + menu.log_location() + "/", PALETTE["hint"])}')


def edit_setting(key: str, reader=input) -> str:
    """Ask for one new value and write it through the settings layer."""
    rows = {row['key']: row for row in settings.list_settings()}
    current = rows[key]['value'] if key in rows else ''
    value = (reader(f"{key} 的新值（当前 {current or '(空)'}，回车取消）: ") or '').strip()
    if not value:
        return '未修改'
    try:
        stored = settings.set_value(key, value)
    except (KeyError, ValueError) as exc:
        return f'修改失败：{exc}'
    return f'已更新 {key} = {stored}'


def edit_provider(name: str, reader=input) -> str:
    """Move one provider up or down in the fallback order."""
    step = (reader(f'{name}：上移(u) / 下移(d) / 回车取消: ') or '').strip().lower()
    delta = {'u': -1, 'up': -1, 'd': 1, 'down': 1}.get(step)
    if delta is None:
        return '未修改'
    try:
        order = settings.move_provider(name, delta)
    except (KeyError, ValueError) as exc:
        return f'修改失败：{exc}'
    return f'优先级：{order}'


def handle(action: str, label: str, screen: str) -> tuple[bool, str, str]:
    """Apply one menu action: (quit now?, screen to show, status line)."""
    if action == menu.QUIT_ACTION:
        return True, screen, ''
    if action == menu.BACK_ACTION:
        return False, menu.parent_of(screen), ''
    target = menu.opens_screen(action)
    if target:
        return False, target, ''
    if action.startswith('@set:'):
        return False, screen, edit_setting(action[len('@set:'):])
    if action.startswith('@move:'):
        return False, screen, edit_provider(action[len('@move:'):])
    if action.startswith(menu.BOOK_ACTION_PREFIX):
        return False, screen, switch_book(action[len(menu.BOOK_ACTION_PREFIX):])
    if action == 'analyze-llm':
        # Overwriting written prose is the only way this action reaches the
        # provider on a finished book, so ask first and default to "no".
        force = confirm('整篇重写已有正文并用 LLM 润色导读/小结？'
                        '（回答 n 则只刷新事实块，正文不动）')
        return False, screen, run_entry(action, label, force=force)
    return False, screen, run_entry(action, label)


def switch_book(root: str) -> str:
    """Make ``root`` the active book for the rest of the session."""
    marker = os.path.join(root, 'data', 'book', 'book.toml')
    if not os.path.isfile(marker):
        return _c(f'没有找到 book.toml：{root}', PALETTE['warn'])
    os.environ['BOOK_ROOT'] = root
    _config.reset(_config.Config(root))
    return _c(f'已切换到 {_config.TITLE or root}', PALETTE['value_ok'])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--once', metavar='ACTION', help='run one action and exit')
    parser.add_argument('--book', default='', help='book root to work on')
    parser.add_argument('--edition', default='', help='manuscript edition to work on')
    args = parser.parse_args(argv)
    if args.book:
        os.environ['BOOK_ROOT'] = os.path.abspath(args.book)
    if args.edition:
        os.environ['BOOK_EDITION'] = args.edition

    if args.once:
        if args.once == 'settings':
            sys.stdout.write(configure())
            return 0
        code, text = actions.run(args.once, book=_config.resolve_book_root(args.book or None),
                                 edition=args.edition)
        sys.stdout.write(text)
        return code

    screen = 'main'
    cursors = {name: menu.default_cursor(name) for name in menu.TITLES}
    status = ''
    while True:
        rows = screen_rows(screen)
        cursor = cursors.get(screen, 0) % len(rows) if rows else 0
        lines = ['\n' + header(), '', screen_title(screen),
                 '', menu_text(screen, cursor)]
        if status:
            lines += ['', status,
                      _c(' 按任意键继续 · 0 收起结果回到菜单', PALETTE['hint'])]
        sys.stdout.write('\n'.join(lines))
        sys.stdout.flush()
        shown_result = bool(status)   # a finished run is on screen right now
        status = ''
        try:
            pressed = keys.normalize(keys.read_key())
        except KeyboardInterrupt:      # Ctrl+C leaves the menu cleanly
            sys.stdout.write('\n')
            return 0

        if pressed in ('q', keys.KEY_CTRL_C):
            return 0
        if pressed in (menu.BACK_KEY, keys.KEY_ESC):
            # A finished run leaves its result on screen: the first `0` puts the
            # menu back, and only the next one leaves the level (or the program).
            if shown_result:
                continue
            if screen == 'main':
                return 0
            screen = menu.parent_of(screen)
            continue
        if pressed == keys.KEY_UP:
            cursors[screen] = (cursor - 1) % len(rows)
            continue
        if pressed == keys.KEY_DOWN:
            cursors[screen] = (cursor + 1) % len(rows)
            continue
        if pressed in ('?', 'h'):
            print(help_text())
            continue
        if pressed == 'r':
            settings._reload()
            status = _c('配置已重新读取', PALETTE['value_ok'])
            continue
        if pressed == 'c':
            screen = menu.SETTINGS_SCREEN
            cursors[screen] = 0
            continue

        if pressed == keys.KEY_ENTER and rows:
            action, label = rows[cursor][1], rows[cursor][2]
        else:
            match = next((row for row in rows if row[0] == pressed.lower()), None)
            if match is None:
                status = _c(f'无效按键 {pressed!r}，按 ? 查看帮助', PALETTE['warn'])
                continue
            action, label = match[1], match[2]

        quit_now, screen, status = handle(action, label, screen)
        if quit_now:
            sys.stdout.write('\n')
            return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
