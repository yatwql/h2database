#!/usr/bin/env python3
"""One place where a toolchain failure becomes an exit code.

A failure has two halves that must stay together: the message a reader sees and
the code a script or a gate reacts to. Raising :class:`ToolError` keeps both
together while the failure travels through ordinary calls, so no layer has to
know whether its caller is a CLI, a gate or a test; :func:`run` turns the pair
into the exit code at the entry point.
"""
from __future__ import annotations

import sys
from collections.abc import Callable, Sequence


class ToolError(SystemExit):
    """A failure reported as one message and one exit code.

    Derived from ``SystemExit`` so that a tool function may raise it from deep
    inside a call chain without changing the exit status a caller already
    observes: ``str(exc)`` is the message, and the interpreter prints it the way
    ``sys.exit(message)`` used to. What is new is that the message and the code
    are one object, so a test can assert them together.
    """

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        # `code` stays the message, as every `sys.exit(message)` caller expects;
        # the numeric status rides alongside it instead of replacing it.
        self.exit_code = code


def run(main: Callable[..., int], argv: Sequence[str] | None = None) -> int:
    """Run an entry point's ``main``, converting a :class:`ToolError`."""
    try:
        code = main() if argv is None else main(list(argv))
    except ToolError as exc:
        print(exc.message, file=sys.stderr)
        return exc.exit_code
    return int(code or 0)
