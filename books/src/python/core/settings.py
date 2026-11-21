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

import importlib
import json
import os
import re
import sys

from lib import _config, _fsutil

BOOK_TOML = os.path.join(_config.BOOK_ROOT, 'data', 'tmpl', 'book.toml')
BASE_JSON = os.path.join(_config.BOOK_ROOT, 'data', 'config', 'base.json')
LLM_PROVIDER_JSON = os.path.join(_config.BOOK_ROOT, 'data', 'config', 'llm_provider.json')

LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR')

# logical key -> (file, section, field, kind, description)
SPEC: dict[str, tuple[str, str, str, str, str]] = {
    'title': (BOOK_TOML, 'book', 'title', 'str', '书名'),
    'version': (BOOK_TOML, 'book', 'version', 'str', '版本号'),
    'manuscript': (BOOK_TOML, 'paths', 'manuscript', 'str', '手稿目录'),
    'dist': (BOOK_TOML, 'paths', 'dist', 'str', '产物目录'),
    'languages': (BASE_JSON, 'sources', 'languages', 'list', '源码语言'),
    'log.level': (BASE_JSON, 'logging', 'level', 'level', '日志级别'),
    'llm.provider': (LLM_PROVIDER_JSON, '', 'default_provider', 'str', '默认 LLM provider'),
}


def _reload() -> None:
    """Re-read configuration so the session sees the change."""
    global _config
    modules = sys.modules
    lib = modules.get('lib')
    for name in ('lib._config', '_config'):
        modules.pop(name, None)
    if lib is not None and hasattr(lib, '_config'):
        delattr(lib, '_config')
    fresh = importlib.import_module('lib._config')
    _config = fresh
    if lib is not None:
        vars(lib)['_config'] = fresh


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


def _read_json(path: str) -> dict:
    try:
        return json.loads(_fsutil.read_text(path))
    except json.JSONDecodeError as exc:
        raise ValueError(f'invalid JSON in {path}: {exc}') from exc


def _write_json(path: str, payload: dict) -> None:
    _fsutil.write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def list_settings() -> list[dict]:
    """Current value and description of every writable key."""
    rows = []
    for key, spec in SPEC.items():
        rows.append({'key': key, 'value': get(key), 'kind': spec[3],
                     'description': spec[4]})
    return rows


def get(key: str) -> str:
    """Read one writable setting as a display string."""
    if key not in SPEC:
        raise KeyError(key)
    path, section, field, _kind, _ = SPEC[key]
    if path.endswith('.json'):
        payload = _read_json(path)
        if section:
            payload = payload.get(section) or {}
        value = payload.get(field)
    else:
        value = _read_toml_value(path, section, field)
    if isinstance(value, list):
        return ','.join(str(item) for item in value)
    return '' if value is None else str(value)


def _validate(key: str, value: str) -> object:
    kind = SPEC[key][3]
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
    if key not in SPEC:
        raise KeyError(key)
    stored = _validate(key, value)
    path, section, field, _kind, _description = SPEC[key]
    if path.endswith('.json'):
        payload = _read_json(path)
        target = payload.setdefault(section, {}) if section else payload
        target[field] = stored
        _write_json(path, payload)
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
    payload = _read_json(LLM_PROVIDER_JSON)
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
    payload = _read_json(LLM_PROVIDER_JSON)
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
    _write_json(LLM_PROVIDER_JSON, payload)
    _reload()
    return ', '.join(order)


def _source_dir() -> str:
    """Configured source tree (empty when not configured)."""
    try:
        return _config.source_tree('src_main')
    except Exception:  # noqa: BLE001 - a missing source tree is not fatal here
        return ''


def summary() -> dict:
    """Book identity plus the settings shown in the UI header."""
    return {
        'title': _config.TITLE,
        'version': _config.VERSION,
        'manuscript': _config.MANUSCRIPT_DIR,
        'dist': _config.DIST_DIR,
        'languages': ','.join(_config.source_languages()),
        'log_level': get('log.level') if 'log.level' in SPEC else '',
        'llm_provider': get('llm.provider'),
        'source_dir': _source_dir(),
        'tool_version': _config.versions()['tool'],
        'source_version': _config.versions()['source'],
        'doc_version': _config.versions()['doc'],
    }
