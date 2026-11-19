"""Make the unittest suite collectable by pytest too.

The tests are plain `unittest` cases that rely on a small bootstrap: the
toolchain layers must be importable as top-level modules and the offline network
guard must be installed before anything touches a socket. `unittest discover`
runs each module with `books/src/test` on sys.path; pytest needs this file to do
the same, otherwise collection fails with ModuleNotFoundError: _fixture.
"""
from __future__ import annotations

import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
if TEST_DIR not in sys.path:
    sys.path.insert(0, TEST_DIR)

import _fixture

_fixture.ensure_tools_path()
