#!/usr/bin/env python3
"""Safe, validated edits of the handful of settings users change often.

Only these keys are writable from the UI/CLI; everything else belongs to the
configuration files and the gates. Each write updates the owning file and
reloads ``lib._config`` so the running session sees the new value.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re

from lib import _config, _fsutil, _volume


def config_dir() -> str:
    """Configuration directory of the active book, resolved per call."""
    return _config.current().config_dir


def book_toml() -> str:
    return _config.current().book_toml


def base_json() -> str:
    return os.path.join(config_dir(), 'base.json')


def provider_json() -> str:
    return os.path.join(config_dir(), 'llm_provider.json')


def settings_json() -> str:
    return os.path.join(config_dir(), 'llm_settings.json')

LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR')

# logical key -> (file, section, field, kind, description)
def spec_table() -> dict[str, tuple[str, str, str, str, str]]:
    """Writable settings and where each one lives, built for the active book."""
    folder = config_dir()
    BOOK_TOML = book_toml()
    BASE_JSON = os.path.join(folder, 'base.json')
    LLM_PROVIDER_JSON = os.path.join(folder, 'llm_provider.json')
    LLM_SETTINGS_JSON = os.path.join(folder, 'llm_settings.json')
    return {
    'title': (BOOK_TOML, 'book', 'title', 'str', '书名'),
    'version': (BOOK_TOML, 'book', 'version', 'str', '版本号'),
    'manuscript': (BOOK_TOML, 'paths', 'manuscript', 'str', '手稿目录'),
    'dist': (BOOK_TOML, 'paths', 'dist', 'str', '产物目录'),
    'languages': (BASE_JSON, 'sources', 'languages', 'list', '源码语言'),
    'log.level': (BASE_JSON, 'logging', 'level', 'level', '日志级别'),
    'llm.provider': (LLM_PROVIDER_JSON, '', 'default_provider', 'str', '默认 LLM provider'),
    'llm.daily_cost_limit': (LLM_SETTINGS_JSON, '', 'daily_cost_limit', 'number',
                             'LLM 每日费用上限（0 = 不限，达到即提醒）'),
    'llm.ingest_prose': (BOOK_TOML, 'llm', 'ingest_prose', 'bool',
                         'ingest 的导读/小结是否用 LLM 起草'),
    }


def _reload() -> None:
    """Re-read the active book's files so the running session sees the change.

    Re-reading replaces re-importing: the book object (and every reference to it)
    survives, so a settings write cannot silently switch books the way a fresh
    module rediscovering its root from the environment could.
    """
    _config.current().refresh()


def _read_toml_value(path: str, section: str, field: str) -> str | None:
    """Read ``[section].field`` from a TOML file with a line-oriented scan."""
    text = _fsutil.read_text(path)
    current = ''
    pattern = re.compile(rf'^\s*{re.escape(field)}\s*=\s*"?(.*?)"?\s*$')
    for line in text.split('\n'):
        header = re.match(r'^\s*\[([^\]]+)\]\s*$', line)
        if header:
            current = header.group(1).strip()
            continue
        if current == section:
            match = pattern.match(line)
            if match:
                return match.group(1)
    return None


def _write_toml_value(path: str, section: str, field: str, value: str) -> None:
    """Replace ``[section].field`` in place, keeping the rest of the file."""
    text = _fsutil.read_text(path)
    lines = text.split('\n')
    current = ''
    replaced = False
    for index, line in enumerate(lines):
        header = re.match(r'^\s*\[([^\]]+)\]\s*$', line)
        if header:
            current = header.group(1).strip()
            continue
        if current == section and re.match(rf'^\s*{re.escape(field)}\s*=', line):
            lines[index] = f'{field} = "{value}"'
            replaced = True
            break
    if not replaced:
        raise KeyError(f'{section}.{field} not found in {path}')
    _fsutil.write_text(path, '\n'.join(lines))


def _write_toml_literal(path: str, section: str, field: str, literal: str) -> None:
    """Replace ``[section].field`` with a bare TOML literal (true/false/number)."""
    text = _fsutil.read_text(path)
    lines = text.split('\n')
    current = ''
    for index, line in enumerate(lines):
        header = re.match(r'^\s*\[([^\]]+)\]\s*$', line)
        if header:
            current = header.group(1).strip()
            continue
        if current == section and re.match(rf'^\s*{re.escape(field)}\s*=', line):
            lines[index] = f'{field} = {literal}'
            _fsutil.write_text(path, '\n'.join(lines))
            return
    # the section may already exist without this key: add the key inside it,
    # otherwise the file ends up with two sections of the same name and stops
    # being valid TOML
    if section:
        header_at = next((i for i, line in enumerate(lines)
                          if re.match(rf'^\s*\[{re.escape(section)}\]\s*$', line)), None)
        if header_at is not None:
            end = next((i for i in range(header_at + 1, len(lines))
                        if re.match(r'^\s*\[', lines[i])), len(lines))
            insert_at = end
            while insert_at > header_at + 1 and not lines[insert_at - 1].strip():
                insert_at -= 1
            lines.insert(insert_at, f'{field} = {literal}')
            _fsutil.write_text(path, '\n'.join(lines))
            return
    # a book that predates the section gets one added, rather than a dead end
    body = '\n'.join(lines).rstrip('\n')
    _fsutil.write_text(path, f'{body}\n\n[{section}]\n{field} = {literal}\n')


def list_settings() -> list[dict]:
    """Current value and description of every writable key."""
    rows = []
    for key, row in spec_table().items():
        rows.append({'key': key, 'value': get(key), 'kind': row[3],
                     'description': row[4]})
    return rows


def get(key: str) -> str:
    """Read one writable setting as a display string."""
    if key not in spec_table():
        raise KeyError(key)
    path, section, field, _kind, _ = spec_table()[key]
    if path.endswith('.json'):
        payload = _fsutil.load_json(path)
        if section:
            payload = payload.get(section) or {}
        value = payload.get(field)
    else:
        value = _read_toml_value(path, section, field)
    if isinstance(value, list):
        return ','.join(str(item) for item in value)
    return '' if value is None else str(value)


def _validate(key: str, value: str) -> object:
    kind = spec_table()[key][3]
    if kind == 'bool':
        text = value.strip().lower()
        if text not in ('true', 'false', 'yes', 'no', '1', '0', 'on', 'off'):
            raise ValueError(f'{key} must be a boolean (true/false)')
        return text in ('true', 'yes', '1', 'on')
    if kind == 'number':
        try:
            number = float(value)
        except ValueError as exc:
            raise ValueError(f'{key} must be a number') from exc
        if number < 0:
            raise ValueError(f'{key} must not be negative')
        return number
    if kind == 'level':
        upper = value.strip().upper()
        if upper not in LEVELS:
            raise ValueError(f'log.level must be one of {", ".join(LEVELS)}')
        return upper
    if kind == 'list':
        items = [item.strip() for item in value.split(',') if item.strip()]
        if not items:
            raise ValueError('languages needs at least one value')
        return items
    if not value.strip():
        raise ValueError(f'{key} must not be empty')
    return value.strip()


def set_value(key: str, value: str) -> str:
    """Validate and persist one setting; returns the stored value."""
    if key not in spec_table():
        raise KeyError(key)
    stored = _validate(key, value)
    path, section, field, kind, _description = spec_table()[key]
    if kind == 'bool':
        _write_toml_literal(path, section, field, 'true' if stored else 'false')
        _reload()
        return 'true' if stored else 'false'
    if path.endswith('.json'):
        payload = _fsutil.load_json(path)
        target = payload.setdefault(section, {}) if section else payload
        target[field] = stored
        _fsutil.dump_json(path, payload)
    else:
        _write_toml_value(path, section, field, str(stored))
    _reload()
    return ','.join(stored) if isinstance(stored, list) else str(stored)


def _priority(spec: dict | None) -> int:
    """Declared fallback priority, tolerating a malformed value."""
    try:
        return int((spec or {}).get('priority', 100))
    except (TypeError, ValueError):
        return 100


def provider_order() -> list[dict]:
    """Providers in fallback order, with the priority the router will read."""
    payload = _fsutil.load_json(provider_json())
    providers = payload.get('providers') or {}
    rows = [{'name': name, 'priority': _priority(spec)} for name, spec in providers.items()]
    return sorted(rows, key=lambda row: (row['priority'], row['name']))


def move_provider(name: str, delta: int) -> str:
    """Move one provider up (-1) or down (+1) in the fallback order.

    The order is persisted as explicit priorities, spaced so a later insert needs
    no renumbering. It is the file the router reads, not a session-only view.
    """
    if delta not in (-1, 1):
        raise ValueError('delta must be -1 or 1')
    payload = _fsutil.load_json(provider_json())
    providers = payload.get('providers') or {}
    if name not in providers:
        raise KeyError(f'unknown provider {name!r}')
    order = [row['name'] for row in provider_order()]
    position = order.index(name)
    target = max(0, min(len(order) - 1, position + delta))
    if target == position:
        return ', '.join(order)
    order.insert(target, order.pop(position))
    for index, provider in enumerate(order):
        providers.setdefault(provider, {})['priority'] = (index + 1) * 10
    payload['providers'] = providers
    _fsutil.dump_json(provider_json(), payload)
    _reload()
    return ', '.join(order)


def _source_dir() -> str:
    """Configured source tree (empty when not configured)."""
    try:
        return _config.source_tree('src_main')
    except Exception:  # noqa: BLE001 - a missing source tree is not fatal here
        return ''


def spend_summary() -> str:
    """Today's LLM spend against the configured ceiling, for the header."""
    from lib import _llm

    try:
        spent = _llm.today_cost()          # already summed in the display currency
        limit = _llm.daily_limit()         # configured in that same currency
        currency = _llm.display_currency()
        symbol = _llm.SYMBOLS.get(currency, '')
    except _llm.LLMError:
        return '—'      # a book without LLM config still gets a header
    left = f'/{symbol}{limit:.2f}' if limit else ''
    return f'{symbol}{spent:.2f}{left}'


def volume_summary() -> str:
    """The manuscript's line count and what would happen if it kept shrinking.

    "Volume", "floor" and "margin" are the gate's own vocabulary; a reader in the
    TUI has to be told the consequence, not the mechanism. So the line states the
    count, then the action that would trip the gate: still N lines to lose before
    the text counts as silently shrunk.
    """
    room = _volume.headroom()
    if room is None:
        return '—'
    return (f'{room["lines"]:,} 行'
            f'（再少 {room["above"]:,} 行即判「内容变薄」）')


def summary() -> dict:
    """Book identity plus the settings shown in the UI header."""
    return {
        'title': _config.TITLE,
        'version': _config.VERSION,
        'manuscript': _config.MANUSCRIPT_DIR,
        'dist': _config.DIST_DIR,
        'languages': ','.join(_config.source_languages()),
        'log_level': get('log.level') if 'log.level' in spec_table() else '',
        'llm_provider': get('llm.provider'),
        'source_dir': _source_dir(),
        'llm_spend': spend_summary(),
        'volume_margin': volume_summary(),
        'tool_version': _config.versions()['tool'],
        'source_version': _config.versions()['source'],
        'doc_version': _config.versions()['doc'],
    }
