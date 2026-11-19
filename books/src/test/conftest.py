"""Make the unittest suite collectable by pytest, with markers from TAGS.

The tests are plain `unittest` cases that rely on a small bootstrap: the
toolchain layers must be importable as top-level modules and the offline network
guard must be installed before anything touches a socket.

Each module declares `TAGS = ('layer:<x>', 'tier:<fast|slow>', …)` (see
`_tags.py`). This file turns those labels into pytest markers, so the same suite
can be selected the way the CI runner does:

    pytest books/src/test -m tier_fast
    pytest books/src/test -m "layer_audit and not tier_slow"
    pytest books/src/test -m scenario
"""
from __future__ import annotations

import importlib
import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
if TEST_DIR not in sys.path:
    sys.path.insert(0, TEST_DIR)

# imported through importlib so this file keeps no import after a statement
_fixture = importlib.import_module('_fixture')
_tags = importlib.import_module('_tags')

_fixture.ensure_tools_path()

# Every label the suite may declare. Unknown labels fail the taxonomy test.
MARKERS = ['scenario', 'edge', 'stability',
           *(f'layer_{layer}' for layer in _tags.LAYERS),
           *(f'tier_{tier}' for tier in _tags.TIERS)]


def pytest_configure(config) -> None:
    for marker in MARKERS:
        config.addinivalue_line('markers', f'{marker}: declared in test TAGS')


def _markers_for(module) -> list[str]:
    labels: tuple[str, ...] = getattr(module, 'TAGS', ())
    names = []
    for label in labels:
        key, _, value = label.partition(':')
        if key in ('layer', 'tier'):
            names.append(f'{key}_{value}')
        elif key in ('scenario', 'edge', 'stability'):
            names.append(key)
    return names


def pytest_collection_modifyitems(items) -> None:
    """Apply each module's TAGS as markers on its test items."""
    try:
        pytest = importlib.import_module('pytest')  # only when pytest drives us
    except ImportError:  # pragma: no cover - unittest-only environments
        return

    for item in items:
        module = getattr(item, 'module', None)
        if module is None:
            continue
        for name in _markers_for(module):
            marker = getattr(pytest.mark, name, None)
            if marker is not None:
                item.add_marker(marker)
