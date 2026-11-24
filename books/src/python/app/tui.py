#!/usr/bin/env python3
"""Terminal UI: two menu levels, live configuration and a compact dashboard.

  python app/tui.py                # interactive
  python app/tui.py --once status  # one action, then exit (scriptable)

Keys: number = run action, 0/Esc = back (quit on the main screen), c = settings,
r = reload config, ? = help, q = quit. After a run its result stays on screen and any
key returns to the menu — except q, which quits. The screen tree lives in core.menu.
Colour is used only on a real terminal and can be disabled with NO_COLOR=1.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import actions, menu, settings
from lib import _config, _errors, _fsutil, status

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
    'shortcut': '1;38;5;51',   # bright cyan: the letter beside a digit
}


def _width(text: str) -> int:
    """Display width: CJK and fullwidth characters take two columns."""
    return sum(2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
               for ch in text)


def _key(text: str, colour: str | None = None,
         letter_colour: str | None = None) -> str:
    """Render one shortcut as [key] so the pressable thing stands out.

    A ``1/A`` pair is drawn with the letter in its own colour: the two keys lead to
    the same action, and the colour is what makes that obvious at a glance.
    """
    if letter_colour and '/' in text:
        digit, letter = text.split('/', 1)
        return (f'[{_c(digit, colour or PALETTE["key"])}/'
                f'{_c(letter, letter_colour)}]')
    return _c(f'[{text}]', colour or PALETTE['key'])


def _c(text: str, code: str) -> str:
    return f'\033[{code}m{text}\033[0m' if USE_COLOR else text


def _header_facts(info: dict) -> list[tuple[str, str]]:
    """Label/value pairs: labels are muted, values near-white."""
    source = info['source_dir'] or '(未配置)'
    return [
        ('源码', f"{source}  {_c('(' + info['source_version'] + ')', PALETTE['hint'])}"),
        ('手稿', info['manuscript']),
        ('产物', info['dist']),
        ('语言', '{}   {} {}   {} {}'.format(
            info['languages'], _c('日志', PALETTE['label']), info['log_level'],
            _c('LLM', PALETTE['label']), info['llm_provider'])),
        ('用量', f"{_c('LLM 今日', PALETTE['label'])} {info['llm_spend']}   "
                 f"{_c('手稿', PALETTE['label'])} {info['volume_margin']}"),
    ]


def _header_titles(info: dict) -> tuple[str, str, str, str]:
    """(rendered product, plain product, rendered book, plain book) lines."""
    updated = _config.tool_updated()
    title = (_c(_config.app_name(), PALETTE['product_accent'])
             + f' · {_config.app_name_zh()}  '
             + _c('v' + info['tool_version'], PALETTE['hint'])
             + (f"  {_c('更新 ' + updated, PALETTE['hint'])}" if updated else ''))
    plain_title = (f' {_config.app_name()} · {_config.app_name_zh()}  '
                   f'v{info["tool_version"]}' + (f'  更新 {updated}' if updated else ''))
    book_date = _config.book_updated()
    book = (f' {_c("书籍", PALETTE["label"])} {_c(info["title"], PALETTE["book"])}'
            f'  {_c("v" + info["version"], PALETTE["hint"])}'
            + (f'  {_c("更新 " + book_date, PALETTE["hint"])}' if book_date else ''))
    plain_book = (f' 书籍 {info["title"]}  v{info["version"]}'
                  + (f'  更新 {book_date}' if book_date else ''))
    return title, plain_title, book, plain_book


def header() -> str:
    """Identity on top, operational facts below, chrome kept quiet."""
    info = settings.summary()
    facts = _header_facts(info)
    label_width = max(_width(label) for label, _value in facts) + 1
    title_rendered, product_plain, book_rendered, book_plain = _header_titles(info)
    inner = max(_width(product_plain), _width(book_plain),
                max(_width(f' {label} {value}') for label, value in facts)) + 1

    def pad(plain: str, rendered: str) -> str:
        return f"{rendered}{' ' * (inner - _width(plain))}"

    def framed(plain: str, rendered: str) -> str:
        edge = _c('│', PALETTE['frame'])
        return edge + pad(plain, rendered) + edge

    def fact_line(label: str, value: str) -> str:
        gap = ' ' * (label_width - _width(label))
        return framed(f' {label}{gap}{value}',
                      f' {_c(label, PALETTE["label"])}{gap}{value}')

    rows = [
        _c('╭' + '─' * inner + '╮', PALETTE['frame']),
        framed(product_plain, ' ' + title_rendered),
        framed(book_plain, book_rendered),
        _c('├' + '─' * inner + '┤', PALETTE['frame']),
        *[fact_line(label, value) for label, value in facts],
        _c('╰' + '─' * inner + '╯', PALETTE['frame']),
    ]
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
                name = f"{cfg.title or '（无标题）'}  [{os.path.basename(root)}]"
            except _config.ConfigError:
                name = f"（配置读不出）  [{os.path.basename(root)}]"
            rows.append((str(index), menu.BOOK_ACTION_PREFIX + root,
                         ('● ' if root == active else '  ') + name))
        return rows + [(menu.BACK_KEY, menu.BACK_ACTION, '返回上一级')]
    if screen == menu.PROVIDERS_SCREEN:
        rows = [(str(index), '@move:' + item['name'],
                 f"{index}. {item['name']}  priority {item['priority']}")
                for index, item in enumerate(settings.provider_order(), start=1)]
        return rows + [(menu.BACK_KEY, menu.BACK_ACTION, '返回上一级')]
    return menu.entries(screen)


def _row_text(screen: str, index: int, key: str, action: str, label: str,
              cursor: int | None) -> str:
    """One menu row: cursor, key, label, and the LLM badge where it applies."""
    marker = '❯' if cursor == index else ' '
    label_style = PALETTE['cursor'] if cursor == index else PALETTE['value']
    llm_row = menu.is_llm(action)
    badge = f" {_c('LLM', PALETTE['llm_badge'])}" if llm_row else ''
    key_label = menu.display_key(screen, key)
    key_colour = PALETTE['llm_key'] if llm_row else None
    return (f" {_c(marker, PALETTE['cursor_bar'])} "
            f"{_key(key_label, key_colour, None if llm_row else PALETTE['shortcut'])}  "
            f"{_c(label, label_style)}{badge}")


def menu_text(screen: str = 'main', cursor: int | None = None) -> str:
    """One screen; `cursor` highlights a row (↑/↓ moves it).

    The main screen reads as groups (source → book, book management, settings);
    a row the groups do not name renders after the last one, so the exit key is
    never tucked inside a group.
    """
    lines: list[str] = []
    rows = screen_rows(screen)
    groups = menu.groups_for(screen)
    if groups:
        index_of = {key: index for index, (key, _action, _label) in enumerate(rows)}
        grouped = {key for _title, keys in groups for key in keys}
        for title, keys in groups:
            members = [index_of[key] for key in keys if key in index_of]
            if not members:
                continue
            lines.append('')
            lines.append(f"   {_c(title, PALETTE['group'])}")
            for index in members:
                key, action, label = rows[index]
                lines.append(_row_text(screen, index, key, action, label, cursor))
        for index, (key, action, label) in enumerate(rows):
            if key in grouped:
                continue
            lines.append(_row_text(screen, index, key, action, label, cursor))
    else:
        for index, (key, action, label) in enumerate(rows):
            lines.append(_row_text(screen, index, key, action, label, cursor))
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
            '非交互场景用 `--once <动作>`，例如 `--once status`。\n'
            '用量行的「手稿」是本稿总行数；括号里是还能再少多少行就会判「内容变薄」'
            '（下限 = 已评审基线 × 0.95）。')


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




def _duration(seconds: float) -> str:
    """`m:ss` for the estimates and the progress stamps."""
    total = int(seconds)
    return f'{total // 60}:{total % 60:02d}'


def confirm(question: str, reader=input) -> bool:
    """y/N prompt for actions worth a second look."""
    answer = (reader(f'{question} [y/N] ') or '').strip().lower()
    return answer in ('y', 'yes', '是')


def run_entry(action: str, label: str, force: bool = False) -> str:
    """Run one action and render the outcome core.menu reports.

    Every line names the artifacts: a confirmation says what is about to be
    overwritten, the progress line says what is being rebuilt, and the outcome says
    whether those files changed. "重建产物" is precise for nobody.
    """
    if action == 'settings':
        return configure()
    rewritten = menu.artifacts(action)
    if menu.needs_confirmation(action):
        question = (f'{label}：将重建 {rewritten}；同名文件会被覆盖，继续？'
                    if rewritten else f'{label} 会重写产物，继续？')
        if not confirm(question):
            return _c(f'已取消，{rewritten or "产物"}未改动', PALETTE['hint'])
    progress = (f'⠿ 正在重建 {rewritten}（{label}）…' if rewritten
                else f'⠿ 正在执行 {label}（{action}）…')
    estimate = menu.estimate(action)
    if estimate:
        sys.stdout.write(_c(f'  预计 {_duration(estimate[0])}–{_duration(estimate[1])}'
                            '（据最近几次同类运行；每步开始与每 10 秒会有进展）',
                            PALETTE['hint']) + '\n')
    sys.stdout.write(_c(progress, PALETTE['hint']) + '\n')
    sys.stdout.flush()
    outcome = _run_with_progress(action, label, force)
    summary = status.render(outcome.ok, outcome.label + ('  --force' if force else ''),
                            outcome.elapsed, outcome.code)
    spent = f'用时 {_duration(outcome.elapsed)}'
    if estimate:
        spent += f'（预计 {_duration(estimate[0])}–{_duration(estimate[1])}）'
    if not rewritten:
        verdict = ('已完成' if outcome.ok else f'失败（退出码 {outcome.code}）') + f'，{spent}'
    else:
        verdict = ((f'已重建：{rewritten}' if outcome.ok
                    else f'失败（退出码 {outcome.code}）：{rewritten} 未更新') + f'，{spent}')
    return (f'\n{outcome.tail}\n{verdict}\n{summary}\n'
            f'{_c("详情见 " + menu.log_location() + "/", PALETTE["hint"])}')


# A stage line in the log is the only honest progress an action can report; showing
# it beats a spinner that says nothing for two minutes.
LOG_LINE = re.compile(r'^\S+ \S+ \w+\s+[\w.]+\s+(.*)$')


def _stage_text(line: str) -> str:
    """The message part of a log line, without the timestamp and level."""
    match = LOG_LINE.match(line)
    return (match.group(1) if match else line).strip()


def _run_with_progress(action: str, label: str, force: bool) -> menu.Outcome:
    """Run the action and print the child's own output as it happens.

    The log tail was a proxy; the child's lines are the real thing and they arrive
    without polling. Consecutive repeats are collapsed so a spinner-free progress
    list stays readable.
    """
    seen: set[str] = set()
    last = ['']
    began = [time.perf_counter()]

    def show(line: str) -> None:
        text = _stage_text(line)
        if not text or text == last[0] or text in seen:
            return
        seen.add(text)
        last[0] = text
        stamp = _duration(time.perf_counter() - began[0])
        sys.stdout.write(f'   [{stamp:>5}] {_c(text[:100], PALETTE["hint"])}\n')
        sys.stdout.flush()

    return menu.run_report(action, label, force=force, on_progress=show)


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
    if action == menu.NEW_BOOK_ACTION:
        return False, screen, new_book()
    if action.startswith(menu.BOOK_ACTION_PREFIX):
        return False, screen, switch_book(action[len(menu.BOOK_ACTION_PREFIX):])
    if action == 'analyze-llm':
        # Overwriting written prose is the only way this action reaches the
        # provider on a finished book, so ask first and default to "no".
        force = confirm('整篇重写已有正文并用 LLM 润色导读/小结？'
                        '（回答 n 则只刷新事实块，正文不动）')
        return False, screen, run_entry(action, label, force=force)
    return False, screen, run_entry(action, label)


def new_book(reader=input) -> str:
    """Create a book from the menu: a name, then a directory or a git URL."""
    name = reader('书名：').strip()
    if not name:
        return _c('已取消：书名不能为空', PALETTE['warn'])
    source = reader('源码目录或 git 地址（可留空）：').strip()
    from core import fetch_source, scaffold  # local: the menu is not the common path
    try:
        target, created = scaffold.create_book(name, source)
    except OSError as exc:
        return _c(f'新建失败：{exc}', PALETTE['warn'])
    message = f'已新建 {target}（{len(created)} 个文件）'
    if scaffold.is_repository(source):
        clone = _config.Config(target).clone_target(source)
        code = fetch_source.main(['--repo', source, '--dir', clone])
        message += '；源码已克隆' if code == 0 else '；源码克隆失败，见上方输出'
    return _c(message, PALETTE['value_ok'])


def switch_book(root: str) -> str:
    """Make ``root`` the active book for the rest of the session."""
    marker = os.path.join(root, 'data', 'book', 'book.toml')
    if not os.path.isfile(marker):
        return _c(f'没有找到 book.toml：{root}', PALETTE['warn'])
    os.environ['BOOK_ROOT'] = root
    _config.reset(_config.Config(root))
    return _c(f'已切换到 {_config.TITLE or root}', PALETTE['value_ok'])


def clear_screen() -> None:
    """Home the cursor and wipe the frame.

    Without this every keypress appends a whole screen below the previous one and
    the menu scrolls out of view. Only a terminal gets the escape sequence: piped
    or captured output stays plain text, which is what the tests and the logs want.
    """
    if USE_COLOR and sys.stdout.isatty():
        sys.stdout.write('\033[H\033[2J')
        sys.stdout.flush()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--once', metavar='ACTION', help='run one action and exit')
    parser.add_argument('--book', default='', help='book root to work on')
    parser.add_argument('--edition', default='', help='manuscript edition to work on')
    return parser


def _once(args) -> int:
    """`--once ACTION`: one action, its output on stdout, exit with its code."""
    if args.once == 'settings':
        sys.stdout.write(configure())
        return 0
    code, text = actions.run(args.once, book=_config.resolve_book_root(args.book or None),
                             edition=args.edition)
    sys.stdout.write(text)
    return code


def _draw(screen: str, cursors: dict[str, int], status: str) -> bool:
    """Draw one frame; returns whether a finished result was on screen."""
    rows = screen_rows(screen)
    cursor = cursors.get(screen, 0) % len(rows) if rows else 0
    lines = ['\n' + header(), '', screen_title(screen), '', menu_text(screen, cursor)]
    if status:
        lines += ['', status, _c(' 按任意键回到菜单', PALETTE['hint'])]
    clear_screen()
    sys.stdout.write('\n'.join(lines))
    sys.stdout.flush()
    return bool(status)


def _row_for(screen: str, pressed: str, rows: list, cursor: int):
    """The (action, label) a keypress selects, or None when it selects nothing."""
    if pressed == keys.KEY_ENTER and rows:
        return rows[cursor][1], rows[cursor][2]
    wanted = menu.resolve(screen, pressed)
    match = next((row for row in rows if row[0] == wanted), None)
    return (match[1], match[2]) if match else None


def _guard_book(args) -> int:
    """Apply the selection; 0 when it is fine, else the exit status.

    Same contract as the CLI and make.py: a bad book root is one message and
    status 2, never a traceback from deep inside the config.
    """
    if args.book:
        os.environ['BOOK_ROOT'] = os.path.abspath(args.book)
        marker = os.path.join(os.environ['BOOK_ROOT'], 'data', 'book', 'book.toml')
        if not os.path.isfile(marker):
            print(f'error: 没找到 book.toml，试过 {os.environ["BOOK_ROOT"]}',
                  file=sys.stderr)
            return 2
    if args.edition:
        os.environ['BOOK_EDITION'] = args.edition
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    invalid = _guard_book(args)
    if invalid:
        return invalid
    if args.once:
        return _once(args)

    screen = 'main'
    cursors = {name: menu.default_cursor(name) for name in menu.TITLES}
    status = ''
    while True:
        shown_result = _draw(screen, cursors, status)
        status = ''
        try:
            pressed = keys.normalize(keys.read_key())
        except KeyboardInterrupt:      # Ctrl+C leaves the menu cleanly
            sys.stdout.write('\n')
            return 0

        if pressed in ('q', keys.KEY_CTRL_C):
            return 0
        if shown_result:
            # A finished run leaves its result on screen, and any key puts the menu
            # back: the result is the last thing a run says, so the next intent is
            # always the menu it came from. Nothing else fires while it is up —
            # pressing `3` again must not start a second build under the old output.
            continue
        if pressed in (menu.BACK_KEY, keys.KEY_ESC):
            if screen == 'main':
                return 0
            screen = menu.parent_of(screen)
            continue

        rows = screen_rows(screen)
        cursor = cursors.get(screen, 0) % len(rows) if rows else 0
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

        chosen = _row_for(screen, pressed, rows, cursor)
        if chosen is None:
            status = _c(f'无效按键 {pressed!r}，按 ? 查看帮助', PALETTE['warn'])
            continue
        quit_now, screen, status = handle(*chosen, screen)
        if quit_now:
            sys.stdout.write('\n')
            return 0


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
