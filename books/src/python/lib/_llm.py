#!/usr/bin/env python3
"""LLM access layer: configuration, provider routing and a thin client.

Configuration lives in two files so policy and secrets stay separate:

  data/config/llm_provider.json   providers, models, routing (scenario/book/chapter)
  data/config/llm_settings.json   generation parameters per scenario/book/chapter

Secrets are read from environment variables named by the provider entry
(``api_key_env``); nothing is stored in the repository. The ``mock`` provider
answers deterministically so the whole pipeline runs offline.

Routing precedence: chapter > book > scenario > default_provider.
"""
from __future__ import annotations

import json
import os
import http.client
from urllib.parse import urlsplit

from lib import _config

CONFIG_DIR = os.path.join(_config.BOOK_ROOT, 'data', 'config')
PROVIDER_PATH = os.path.join(CONFIG_DIR, 'llm_provider.json')
SETTINGS_PATH = os.path.join(CONFIG_DIR, 'llm_settings.json')


class LLMError(RuntimeError):
    """Raised when a provider cannot be used (missing config or credentials)."""


def _load(path: str) -> dict:
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except OSError as exc:
        raise LLMError(f'missing LLM config: {path}') from exc
    except json.JSONDecodeError as exc:
        raise LLMError(f'invalid JSON in {path}: {exc}') from exc


def providers() -> dict:
    """Provider table with routing rules."""
    return _load(PROVIDER_PATH)


def settings() -> dict:
    """Generation settings per scenario/book/chapter."""
    return _load(SETTINGS_PATH)


def _pick(mapping: dict | None, key: str | None) -> str | None:
    if not mapping or not key:
        return None
    return mapping.get(key)


def resolve(scenario: str, book: str | None = None,
            chapter: str | None = None) -> dict:
    """Resolve provider + parameters for one call (chapter > book > scenario)."""
    cfg = providers()
    routing = cfg.get('routing') or {}
    provider = (_pick(routing.get('chapter'), chapter)
                or _pick(routing.get('book'), book)
                or _pick(routing.get('scenario'), scenario)
                or cfg.get('default_provider'))
    if not provider:
        raise LLMError('no provider resolved and no default_provider configured')
    spec = (cfg.get('providers') or {}).get(provider)
    if spec is None:
        raise LLMError(f'unknown provider {provider!r}')

    cfg_settings = settings()
    merged = {**(cfg_settings.get('defaults') or {}),
              **((cfg_settings.get('scenarios') or {}).get(scenario) or {}),
              **((cfg_settings.get('books') or {}).get(book or '') or {}),
              **((cfg_settings.get('chapters') or {}).get(chapter or '') or {})}
    return {'provider': provider, 'spec': spec, 'settings': merged}


def _mock(prompt: str, spec: dict, params: dict) -> str:
    """Deterministic offline answer: enough to exercise the pipeline."""
    return (f'[mock:{spec.get("kind", "mock")}] '
            f'{prompt.strip()[:80]} …（{params.get("max_tokens", 0)} tokens 预算）')


def _post_json(url: str, payload: dict, api_key: str, timeout: float) -> dict:
    """POST JSON to an https endpoint and return the decoded response."""
    parts = urlsplit(url)
    if parts.scheme != 'https':
        raise LLMError(f'provider endpoint must be https: {url}')
    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json',
               'Authorization': f'Bearer {api_key}'}
    connection = http.client.HTTPSConnection(parts.hostname or '', parts.port or 443,
                                             timeout=timeout)
    try:
        connection.request('POST', parts.path or '/', body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
    except OSError as exc:
        raise LLMError(f'provider request failed: {exc}') from exc
    finally:
        connection.close()
    try:
        return json.loads(raw.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LLMError(f'provider returned invalid JSON: {exc}') from exc


def complete(prompt: str, scenario: str = 'chapter-draft',
             book: str | None = None, chapter: str | None = None,
             model: str | None = None) -> str:
    """Send a prompt through the resolved provider and return the text."""
    resolved = resolve(scenario, book=book, chapter=chapter)
    spec, params = resolved['spec'], resolved['settings']
    kind = spec.get('kind', 'mock')

    if kind == 'mock':
        return _mock(prompt, spec, params)

    api_key_env = spec.get('api_key_env')
    api_key = os.environ.get(api_key_env or '', '')
    if not api_key:
        raise LLMError(f'provider {resolved["provider"]!r} needs ${api_key_env}')

    model_name = model or (spec.get('models') or [''])[0]
    payload = {
        'model': model_name,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': params.get('temperature', 0.3),
        'max_tokens': params.get('max_tokens', 2048),
    }
    data = _post_json(spec['base_url'].rstrip('/') + '/chat/completions',
                      payload, api_key, float(params.get('timeout_s', 60)))
    try:
        return data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f'unexpected provider response: {data!r}') from exc


def status() -> dict:
    """Non-secret summary for CLIs and the web UI."""
    cfg = providers()
    return {
        'default_provider': cfg.get('default_provider'),
        'providers': sorted(cfg.get('providers') or {}),
        'routing': cfg.get('routing') or {},
        'scenarios': sorted(settings().get('scenarios') or {}),
    }
