#!/usr/bin/env python3
"""One place that launches the browser the renderers need.

Two rules, both about leaving the checkout clean:

* the browser runs with the book's tmp directory as its working directory, so the
  crash reports, shader caches and scratch files it writes land where they are
  gitignored and cleaned together — a crashed render dropped a 36 MB `core.3077190`
  into the repository root, which nobody wants to find;
* the child starts with its core-dump limit at zero, so a crash cannot write that
  file in the first place. Linux and macOS only; the guard is skipped elsewhere.
"""

from __future__ import annotations

import contextlib
import os

from lib import _config

# The flags every launch here needs: no sandbox (containers and CI), no setuid
# sandbox. Kept as data so a caller can extend them without copying the list.
LAUNCH_ARGS = ("--no-sandbox", "--disable-setuid-sandbox")


def _no_core_dumps() -> None:
    """A crashed render must not write a core file into the checkout.

    The limit is set in this process: the browser inherits it at fork/exec, and
    Playwright's launch() accepts neither `cwd` nor `preexec_fn`.
    """
    with contextlib.suppress(ImportError, ValueError, OSError):
        import resource

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def launch(playwright, *, args=LAUNCH_ARGS, **kwargs):
    """Headless Chromium whose scratch space is the book's tmp directory."""
    folder = _config.tmp_dir()
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        # a read-only checkout still renders: the browser keeps the default tmp dir
        folder = ""
    _no_core_dumps()
    env = dict(kwargs.pop("env", None) or os.environ)
    if folder:
        env["TMPDIR"] = folder
    return playwright.chromium.launch(headless=True, args=list(args), env=env, **kwargs)
