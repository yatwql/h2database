#!/usr/bin/env python3
"""Shared test bases: a fixture book, and a runner for scripts in-process."""

from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

_fixture.ensure_tools_path()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_script(self, script: str, *args: str, env: dict | None = None):
        if env is None:
            return _fixture.run_inproc(self.root, script, *args)
        previous = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            return _fixture.run_inproc(self.root, script, *args)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def declare(self, name: str) -> None:
        """List a probe chapter in book.toml: `[chapters].files` is the contract."""
        path = os.path.join(self.root, "data", "book", "book.toml")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        marker = '    "ch2-test.md",\n]'
        assert marker in text, "fixture book.toml lost its chapter list"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(marker, f'    "ch2-test.md",\n    "{name}",\n]', 1))

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path


class ScriptTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_script(self, script: str, *args: str) -> tuple[int, str]:
        return _fixture.run_inproc(self.root, script, *args)

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def read(self, *parts: str) -> str:
        with open(self.path(*parts), encoding="utf-8") as fh:
            return fh.read()


class FixtureCase(Base):
    """A built fixture book plus the helpers a case needs to look inside it.

    `setUp`, `write`, `run_script` and `declare` come from `Base`: the same fixture
    contract whether a case needs a bare book or the module-loading helpers below.
    """

    def dist(self, name: str) -> str:
        return os.path.join(self.root, "dist", name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def read(self, path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class TempFile:
    """Context manager that materialises fixture text to a temp .md file."""

    def __init__(self, text: str):
        self.text = text

    def __enter__(self) -> str:
        self._tmp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        self._tmp.write(self.text)
        self._tmp.close()
        return self._tmp.name

    def __exit__(self, *exc) -> None:
        os.unlink(self._tmp.name)
