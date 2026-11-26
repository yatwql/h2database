#!/usr/bin/env python3
"""Portability probes: the toolchain must survive a non-UTF-8 environment.

Two independent checks, both cheap:

  ENCODING   every text `open()` in the toolchain names its encoding (PEP 597);
             a locale-dependent default is how a Windows CP936 box corrupts a
             manuscript that reads fine on Linux
  LOCALE     the entry points still run with `LC_ALL=C` and
             `PYTHONIOENCODING=ascii`: Chinese output must not crash the process

Usage:
  python portability.py            # report + exit code
  python portability.py --json

Exit codes: 0 clean, 1 problems found, 2 usage error.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_MODES = ("r", "w", "a", "x", "rt", "wt", "at", "xt")
ASCII_ENV = {"LC_ALL": "C", "LANG": "C", "PYTHONIOENCODING": "ascii"}


def python_files() -> list[str]:
    return _fsutil.python_files(PY_ROOT)


def opens_without_encoding(path: str) -> list[tuple[int, str]]:
    """(line, call text) for every text-mode open() that omits encoding=."""
    try:
        tree = ast.parse(_fsutil.read_text(path))
    except SyntaxError:
        return []
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != "open" or len(node.args) < 2:
            continue
        mode = node.args[1]
        if not isinstance(mode, ast.Constant) or not isinstance(mode.value, str):
            continue
        if mode.value not in TEXT_MODES:
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        found.append((node.lineno, ast.unparse(node)[:80]))
    return found


def encoding_problems() -> list[dict]:
    problems = []
    for path in python_files():
        for lineno, call in opens_without_encoding(path):
            problems.append(
                {
                    "check": "ENCODING",
                    "file": os.path.relpath(path, os.path.join(_config.BOOK_ROOT, "..")),
                    "line": lineno,
                    "detail": f"open() without encoding=: {call}",
                }
            )
    return problems


def locale_probe(timeout: float = 60.0) -> list[dict]:
    """Run the CLI under an ASCII locale; a crash means non-ASCII output is unsafe."""
    problems: list[dict] = []
    env = dict(os.environ, **ASCII_ENV)
    for script, args in (("app/cli.py", ["status"]), ("app/tui.py", ["--once", "status"])):
        path = os.path.join(PY_ROOT, script)
        if not os.path.isfile(path):
            continue
        try:
            result = subprocess.run(
                [sys.executable, path, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            problems.append(
                {
                    "check": "LOCALE",
                    "file": script,
                    "line": 0,
                    "detail": f"probe failed to run: {exc}",
                }
            )
            continue
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            problems.append(
                {
                    "check": "LOCALE",
                    "file": script,
                    "line": 0,
                    "detail": f"exit {result.returncode} under LC_ALL=C: "
                    f"{detail[-1][:120] if detail else 'no output'}",
                }
            )
    return problems


def scan(timeout: float = 60.0) -> list[dict]:
    return encoding_problems() + locale_probe(timeout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    problems = scan()
    if args.json:
        print(
            json.dumps({"count": len(problems), "problems": problems}, ensure_ascii=False, indent=2)
        )
        return 0 if not problems else 1

    if not problems:
        print("✅ 移植性通过（open() 均显式 encoding；ASCII locale 下入口可运行）")
        return 0
    print(f"移植性问题 {len(problems)} 处：")
    for item in problems[:40]:
        location = f"{item['file']}:{item['line']}" if item["line"] else item["file"]
        print(f"  [{item['check']}] {location}  {item['detail']}")
    return 1


if __name__ == "__main__":
    sys.exit(_errors.run(main, sys.argv[1:]))
