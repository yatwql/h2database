#!/usr/bin/env python3
"""LLM access layer: configuration, provider routing and a thin client.

Configuration lives in two files so policy and secrets stay separate:

  data/config/llm_provider.json   providers, models, routing (scenario/book/chapter)
  data/config/llm_settings.json   generation parameters per scenario/book/chapter

Secrets come from two places, resolved in this order:

  1. the environment variable named by the provider entry (``api_key_env``)
  2. ``data/config/llm_key.json`` (gitignored, shape: ``{"keys": {provider: key}}``)

Nothing secret is ever committed: ``llm_key.json`` is ignored by git and the
``llm_policy`` gate fails if a key file is tracked. The shipped config points
at real providers; a ``kind: mock`` entry can be added for offline runs and is
what the test fixtures use.

Routing precedence: chapter > book > scenario > default_provider.
"""
from __future__ import annotations

import http.client
import json
import os
import time
from urllib.parse import urlsplit

from lib import _config, _fsutil, _log

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
    entry = (_pick(routing.get('chapter'), chapter)
             or _pick(routing.get('book'), book)
             or _pick(routing.get('scenario'), scenario))
    thinking_route = None
    if isinstance(entry, dict):
        thinking_route = entry.get('thinking')
        provider = entry.get('provider')
    else:
        provider = entry
    provider = provider or cfg.get('default_provider')
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
    thinking = (thinking_route
                or ((cfg_settings.get('thinking') or {}).get(chapter or ''))
                or ((cfg_settings.get('thinking') or {}).get(book or ''))
                or ((cfg_settings.get('thinking') or {}).get(scenario))
                or merged.get('thinking') or 'low')
    levels = cfg.get('thinking_levels') or ['off', 'low', 'medium', 'high']
    if thinking not in levels:
        raise LLMError(f'unknown thinking level {thinking!r}; expected one of {levels}')
    merged['thinking'] = thinking
    return {'provider': provider, 'spec': spec, 'settings': merged}


def _ordered_providers(preferred: str) -> list[str]:
    """Preferred provider first, then the rest by ascending ``priority``."""
    table = providers().get('providers') or {}
    others = sorted(
        (name for name in table if name != preferred),
        key=lambda name: (table[name].get('priority', 100), name))
    return [preferred, *others]


_LAST_CALL: dict[str, float] = {}


def _respect_pacing(provider: str, spec: dict) -> None:
    """Honour a provider's declared min_interval (subscription endpoints).

    This is honest client-side throttling: the provider's own pacing numbers are
    applied before the request instead of hammering the endpoint.
    """
    pacing = spec.get('pacing') or {}
    interval = _safe_float(pacing.get('min_interval'))
    if interval <= 0:
        return
    previous = _LAST_CALL.get(provider)
    now = time.monotonic()
    if previous is not None and now - previous < interval:
        time.sleep(interval - (now - previous))
    _LAST_CALL[provider] = time.monotonic()


def _mock(prompt: str, spec: dict, params: dict) -> str:
    """Deterministic offline answer: enough to exercise the pipeline."""
    return (f'[mock:{spec.get("kind", "mock")}/{params.get("thinking", "low")}] '
            f'{prompt.strip()[:80]} …（{params.get("max_tokens", 0)} tokens 预算）')


def _post_json(url: str, payload: dict, api_key: str, timeout: float,
               headers: dict | None = None) -> dict:
    """POST JSON to an https endpoint and return the decoded response."""
    parts = urlsplit(url)
    if parts.scheme != 'https':
        raise LLMError(f'provider endpoint must be https: {url}')
    body = json.dumps(payload).encode('utf-8')
    headers = dict(headers or {'Content-Type': 'application/json',
                               'Authorization': f'Bearer {api_key}'})
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


def key_file() -> dict:
    """Contents of the local key file (empty when it is absent)."""
    path = _config.key_file()
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _key_block(provider: str, spec: dict) -> dict:
    """Credential block for a provider (``providers.<ref>`` in the key file)."""
    data = key_file()
    ref = spec.get('credentials_ref') or provider
    block = (data.get('providers') or {}).get(ref)
    if isinstance(block, dict):
        return block
    flat = data.get('keys') or {}
    return {'api_key': flat.get(provider, '')} if flat else {}


def _api_key(provider: str, spec: dict) -> str:
    """Environment variable first, then the gitignored key file."""
    env_name = spec.get('api_key_env')
    if env_name:
        value = os.environ.get(env_name, '')
        if value:
            return value
    block = _key_block(provider, spec)
    if block.get('api_key'):
        return str(block['api_key'])
    return str((key_file().get('keys') or {}).get(provider, '') or '')


def _model_for(provider: str, spec: dict, override: str | None = None) -> str:
    """Caller override > key-file override > the provider's configured model."""
    if override:
        return override
    block = _key_block(provider, spec)
    if block.get('model'):
        return str(block['model'])
    models = spec.get('models') or ['']
    return str(models[0] or '')


def _endpoint_for(provider: str, spec: dict) -> str:
    """Provider config is authoritative; a key-file endpoint is an override."""
    block = _key_block(provider, spec)
    return str(block.get('endpoint') or spec.get('base_url') or '').rstrip('/')


def _complete_anthropic(prompt: str, provider: str, spec: dict, params: dict,
                        model: str | None) -> str:
    """Anthropic Messages API (``/v1/messages``) with x-api-key auth."""
    api_key = _api_key(provider, spec)
    if not api_key:
        raise LLMError(f'provider {provider!r} has no key: set '
                       f'${spec.get("api_key_env")} or add it to '
                       f'data/config/llm_key.json')
    payload = {
        'model': _model_for(provider, spec, model),
        'max_tokens': params.get('max_tokens', 2048),
        'temperature': params.get('temperature', 0.3),
        'messages': [{'role': 'user', 'content': prompt}],
    }
    headers = {'Content-Type': 'application/json',
               'x-api-key': api_key,
               'anthropic-version': spec.get('anthropic_version', '2023-06-01')}
    data = _post_json(_endpoint_for(provider, spec) + '/v1/messages', payload,
                      api_key, _safe_float(params.get('timeout_s'), 60.0) or 60.0,
                      headers=headers)
    try:
        blocks = data['content']
        text = ''.join(part.get('text', '') for part in blocks
                       if isinstance(part, dict) and part.get('type', 'text') == 'text')
    except (KeyError, TypeError) as exc:
        raise LLMError(f'unexpected provider response: {data!r}') from exc
    if not text:
        raise LLMError(f'provider returned no text: {data!r}')
    usage = data.get('usage') or {}
    _record(provider, payload['model'], str(params.get('scenario', '')),
            _safe_int(usage.get('input_tokens'), estimate_tokens(prompt)),
            _safe_int(usage.get('output_tokens'), estimate_tokens(text)))
    return text


def _attempt(prompt: str, provider: str, spec: dict, params: dict,
             model: str | None) -> str:
    """One provider attempt (mock / anthropic / openai-compatible)."""
    kind = spec.get('kind', 'mock')
    if kind == 'mock':
        return _mock(prompt, spec, params)

    _respect_pacing(provider, spec)
    if kind == 'anthropic':
        return _complete_anthropic(prompt, provider, spec, params, model)

    api_key = _api_key(provider, spec)
    if not api_key:
        hint = spec.get('api_key_env') or 'llm_key.json'
        raise LLMError(f'provider {provider!r} has no key: '
                       f'set ${spec.get("api_key_env")} or add it to '
                       f'data/config/llm_key.json ({hint})')

    payload = {
        'model': _model_for(provider, spec, model),
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': params.get('temperature', 0.3),
        'max_tokens': params.get('max_tokens', 2048),
        'reasoning_effort': params.get('thinking', 'low'),
    }
    data = _post_json(_endpoint_for(provider, spec) + '/chat/completions',
                      payload, api_key, _safe_float(params.get('timeout_s'), 60.0) or 60.0)
    try:
        text = data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f'unexpected provider response: {data!r}') from exc
    usage = data.get('usage') or {}
    _record(provider, payload['model'], str(params.get('scenario', '')),
            _safe_int(usage.get('prompt_tokens'), estimate_tokens(prompt)),
            _safe_int(usage.get('completion_tokens'), estimate_tokens(text)))
    return text


LOG = _log.get_logger('llm')

def pricing_path() -> str:
    """Resolved per call: the book root can change (fixtures, multi-book)."""
    return os.path.join(_config.BOOK_ROOT, 'data', 'config', 'llm_pricing.json')


def usage_log() -> str:
    return os.path.join(_config.BOOK_ROOT, 'logs', 'llm-usage.jsonl')
# ~3.5 characters per token is the usual rule of thumb for mixed Chinese/English
CHARS_PER_TOKEN = 3.5

_last_usage: dict = {}
_totals: dict = {'calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'cost': 0.0}


def pricing() -> dict:
    """Model price table, or an empty table when the book ships none."""
    path = pricing_path()
    if not os.path.isfile(path):
        return {}
    try:
        return _load(path)
    except LLMError:
        return {}


def price_of(model: str) -> dict:
    """Price entry for one model, empty when unpriced."""
    table = pricing()
    return ((table.get('models') or {}).get(model) or {})


def cost_of(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Cost of one call in the pricing file's currency; None when unpriced."""
    entry = price_of(model)
    if not entry:
        return None
    return (prompt_tokens * _safe_float(entry.get('input_per_mtok'))
            + completion_tokens * _safe_float(entry.get('output_per_mtok'))) / 1_000_000


def _safe_float(value, default: float = 0.0) -> float:
    """Same contract as ``_safe_int`` for prices and ceilings."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    """Provider-reported numbers are untrusted: a malformed usage block must not
    turn a successful call into a crash."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def estimate_tokens(text: str) -> int:
    """Rough prompt size, good enough to choose between "cents" and "dollars"."""
    return max(1, int(len(text or '') / CHARS_PER_TOKEN))


def estimate(prompt: str, scenario: str = 'chapter-draft') -> dict:
    """Pre-run guess: prompt tokens now, completion up to the scenario budget."""
    resolved = resolve(scenario)
    budget = _safe_int(resolved['settings'].get('max_tokens'), 2048) or 2048
    prompt_tokens = estimate_tokens(prompt)
    model = _model_for(resolved['provider'],
                       providers()['providers'][resolved['provider']])
    low = cost_of(model, prompt_tokens, budget // 2)
    high = cost_of(model, prompt_tokens, budget)
    return {'model': model, 'prompt_tokens': prompt_tokens, 'max_tokens': budget,
            'cost_low': convert(low, pricing().get('currency', 'USD')) if low is not None else None,
            'cost_high': convert(high, pricing().get('currency', 'USD')) if high is not None else None,
            'currency': display_currency()}


SYMBOLS = {'CNY': '¥', 'USD': '$', 'EUR': '€'}


def display_currency() -> str:
    """Currency the reports are shown in (default CNY)."""
    return str(pricing().get('display_currency') or 'CNY')


def fx_rates() -> dict:
    """Currency -> CNY anchor. A missing rate means "no conversion known"."""
    rates = dict(pricing().get('fx') or {})
    rates.setdefault('CNY', 1.0)
    return rates


def convert(value: float, source: str, target: str | None = None) -> float | None:
    """Convert between currencies through the CNY anchor; None when unknown."""
    target = target or display_currency()
    if source == target:
        return value
    rates = fx_rates()
    if source not in rates or target not in rates:
        return None
    return value * rates[source] / rates[target]


def _money(value: float | None, currency: str | None = None) -> str:
    """Format an amount in the display currency, naming the model's own one too."""
    if value is None:
        return '未定价'
    source = currency or display_currency()
    shown = display_currency()
    converted = convert(value, source, shown)
    if converted is None:
        return f'{value:.4f} {source}'
    symbol = SYMBOLS.get(shown, '')
    return f'{symbol}{converted:.4f}' + ('' if symbol else f' {shown}')


def _record(provider: str, model: str, scenario: str, prompt_tokens: int,
            completion_tokens: int) -> None:
    """Remember one call: module totals, a one-line log row, and the last usage."""
    cost = cost_of(model, prompt_tokens, completion_tokens)
    currency = pricing().get('currency', 'USD')
    shown_currency = display_currency()
    cost_display = convert(cost, currency) if cost is not None else None
    global _last_usage
    _last_usage = {'provider': provider, 'model': model, 'scenario': scenario,
                   'prompt_tokens': prompt_tokens,
                   'completion_tokens': completion_tokens,
                   'cost': cost, 'currency': currency,
                   'cost_display': cost_display, 'display_currency': shown_currency}
    _totals['calls'] += 1
    _totals['prompt_tokens'] += prompt_tokens
    _totals['completion_tokens'] += completion_tokens
    _totals['cost'] += cost_display or 0.0
    try:
        log = usage_log()
        _fsutil.ensure_dir(os.path.dirname(log))
        with open(log, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'at': _utcnow(), **_last_usage},
                                ensure_ascii=False) + '\n')
    except OSError as exc:  # pragma: no cover - a read-only log dir must not break a call
        LOG.debug('cannot record usage: %s', exc)


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def usage_line() -> str:
    """One line for the result area: what this call cost, and what today costs."""
    if not _last_usage:
        return ''
    tokens = _last_usage['prompt_tokens'] + _last_usage['completion_tokens']
    spent = _money(_last_usage['cost'], _last_usage['currency'])
    return (f"LLM：{_last_usage['model'] or '?'} 本次 {tokens} token"
            f"（入 {_last_usage['prompt_tokens']} / 出 {_last_usage['completion_tokens']}）"
            f" ≈ {spent}；今日累计 ≈ {_money(today_cost(), _last_usage['currency'])}")


def take_totals() -> dict:
    """Snapshot the session totals, for diffing around a multi-call run."""
    return dict(_totals)


def since(marker: dict) -> dict:
    """Calls, tokens and cost added since a ``take_totals()`` snapshot."""
    return {key: _totals[key] - marker.get(key, 0) for key in _totals}


def summary_line(marker: dict) -> str:
    """One line summarising everything a multi-call run spent."""
    delta = since(marker)
    if not delta['calls']:
        return 'LLM：本次未调用'
    tokens = delta['prompt_tokens'] + delta['completion_tokens']
    currency = pricing().get('currency', 'USD')
    return (f"LLM：本次 {delta['calls']} 次调用，{tokens} token"
            f"（入 {delta['prompt_tokens']} / 出 {delta['completion_tokens']}）"
            f" ≈ {_money(delta['cost'], currency)}；今日累计 ≈ "
            f"{_money(today_cost(), currency)}")


def today_cost() -> float:
    """Sum of today's recorded calls, read from the usage log (survives restarts)."""
    path = usage_log()
    if not os.path.isfile(path):
        return 0.0
    today = _utcnow()[:10]
    total = 0.0
    try:
        for line in _fsutil.read_lines(path):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if str(row.get('at', '')).startswith(today):
                total += _safe_float(row.get('cost_display') or row.get('cost'))
    except OSError:
        return 0.0
    return total


def daily_limit() -> float:
    """Soft daily money ceiling from llm_settings.json (0 disables it)."""
    return _safe_float(settings().get('daily_cost_limit'))


def budget_line() -> str:
    """A warning line once today's spend reaches the configured ceiling."""
    limit = daily_limit()
    if not limit:
        return ''
    spent = today_cost()
    if spent < limit:
        return ''
    currency = pricing().get('currency', 'USD')
    return (f'⚠ 今日 LLM 花费 ≈ {_money(spent, currency)} 已达上限 '
            f'{_money(limit, currency)}（llm_settings.json → daily_cost_limit）')


def complete(prompt: str, scenario: str = 'chapter-draft',
             book: str | None = None, chapter: str | None = None,
             model: str | None = None) -> str:
    """Send a prompt, falling back along the priority chain on failure."""
    resolved = resolve(scenario, book=book, chapter=chapter)
    params = resolved['settings']
    table = providers().get('providers') or {}
    chain = [name for name in _ordered_providers(resolved['provider'])
             if name in table]
    last_error: Exception | None = None
    params = {**params, 'scenario': scenario}
    for provider in chain:
        try:
            return _attempt(prompt, provider, table[provider], params, model)
        except LLMError as exc:
            last_error = exc
            continue
    raise LLMError(f'all providers failed, last error: {last_error}')


def status() -> dict:
    """Non-secret summary for CLIs and the web UI."""
    cfg = providers()
    data = key_file()
    blocks = data.get('providers') or {}
    flat_keys = data.get('keys') or {}
    configured = sorted(name for name, block in blocks.items()
                        if isinstance(block, dict) and block.get('api_key'))
    configured += sorted(name for name, value in flat_keys.items()
                         if value and name not in configured)
    return {
        'key_source': _config.key_file() if os.path.exists(_config.key_file()) else '',
        'default_provider': cfg.get('default_provider'),
        'providers': sorted(cfg.get('providers') or {}),
        'routing': cfg.get('routing') or {},
        'scenarios': sorted(settings().get('scenarios') or {}),
        'keys_configured': configured,
    }
