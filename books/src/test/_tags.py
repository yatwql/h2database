"""Test taxonomy: every suite declares what it covers and how expensive it is.

Two labels, both required (enforced by test_meta_taxonomy):

  layer:<lib|core|ingest|manuscript|audit|render|app|pipeline|infra>
      the part of the toolchain the suite exercises
  tier:<fast|slow>
      fast  — no browser, no pandoc, no network; runs in the default suite
      slow  — needs chromium/pandoc or spawns the whole pipeline

Additional free-form labels describe the scenario (`scenario:matrix`,
`edge:bom`, `stability:idempotent`). Selection helpers keep the runner simple:

    python -m unittest discover -s books/src/test -t books/src/test
    python -m unittest discover ... -k tier_slow     # unittest-native filter
"""
from __future__ import annotations

LAYERS = ('lib', 'core', 'ingest', 'manuscript', 'audit', 'render', 'app',
          'pipeline', 'infra')
TIERS = ('fast', 'slow')


def tag(*labels: str):
    """Attach labels to a test class or function (`@tag('scenario:matrix')`)."""

    def decorate(target):
        existing = tuple(getattr(target, '__tags__', ()))
        target.__tags__ = existing + tuple(labels)
        return target

    return decorate


def tags_of(target) -> tuple[str, ...]:
    """Labels declared on the object plus any inherited from its class."""
    found = list(getattr(target, '__tags__', ()))
    owner = getattr(target, '__self__', None)
    if owner is not None:
        found += list(getattr(type(owner), 'TAGS', ()))
    return tuple(dict.fromkeys(found))


def validate(labels) -> list[str]:
    """Return the reasons a label set is invalid (empty when it is fine)."""
    problems = []
    layers = [label.split(':', 1)[1] for label in labels
              if isinstance(label, str) and label.startswith('layer:')]
    tiers = [label.split(':', 1)[1] for label in labels
             if isinstance(label, str) and label.startswith('tier:')]
    if len(layers) != 1:
        problems.append(f'expected exactly one layer label, got {layers}')
    elif layers[0] not in LAYERS:
        problems.append(f'unknown layer {layers[0]!r}')
    if len(tiers) != 1:
        problems.append(f'expected exactly one tier label, got {tiers}')
    elif tiers[0] not in TIERS:
        problems.append(f'unknown tier {tiers[0]!r}')
    return problems


def layer_of(name: str) -> str:
    """Infer the layer from a test module filename (`test_audit_links.py`)."""
    stem = name.removesuffix('.py')
    parts = stem.split('_')
    if len(parts) > 1 and parts[1] in LAYERS:
        return parts[1]
    if 'pipeline' in stem:
        return 'pipeline'
    return 'infra'
