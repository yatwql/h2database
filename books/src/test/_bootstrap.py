#!/usr/bin/env python3
"""Test bootstrap: make books/tools importable from the test modules."""
import os
import sys

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
for _path in (TOOLS_DIR, *(os.path.join(TOOLS_DIR, _sub)
                          for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'))):
    if _path not in sys.path:
        sys.path.insert(0, _path)

BOOK_ROOT = os.path.dirname(TOOLS_DIR)
