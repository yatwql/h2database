"""Single-key terminal input for the interactive menu.

One press is one event: the menu never waits for Enter. Supported keys:

    ↑ / ↓        move the cursor            (also ESC [ A / ESC [ B / ESC O A / ESC O B)
    Enter        run the highlighted entry  (\\r or \\n)
    Esc          cancel / leave a prompt
    Ctrl+C       quit
    0-9, c, r, ? single-character shortcuts

Two modes keep the same contract:

* **tty** — cbreak mode, one byte read at a time, escape sequences parsed with a
  short timeout so a lone Esc is not mistaken for a sequence prefix.
* **not a tty** (pipes, tests, CI) — a line is read and its first character is
  returned, so scripted input (`printf 'q\\n' | bookctl tui`) still works.
"""
from __future__ import annotations

import os
import sys

KEY_UP = 'KEY_UP'
KEY_DOWN = 'KEY_DOWN'
KEY_ENTER = 'KEY_ENTER'
KEY_ESC = 'KEY_ESC'
KEY_CTRL_C = 'KEY_CTRL_C'
KEY_UNKNOWN = 'KEY_UNKNOWN'

_SEQUENCES = {
    '\x1b[A': KEY_UP,
    '\x1b[B': KEY_DOWN,
    '\x1bOA': KEY_UP,
    '\x1bOB': KEY_DOWN,
}
_ESC_TIMEOUT = 0.05


def interactive() -> bool:
    """True when a real terminal is attached to stdin."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def decode_key(raw: str) -> str:
    """Map a raw key byte (or an escape sequence) to its key name.

    Pure so the mapping can be tested without a terminal; the reader only adds
    the timing that decides whether a bare ESC ends a sequence.
    """
    if raw == '\x03':
        return KEY_CTRL_C
    if raw in ('\r', '\n'):
        return KEY_ENTER
    if raw.startswith('\x1b'):
        return _SEQUENCES.get(raw, KEY_ESC)
    return raw


def _posix_getch() -> str:
    """Read one key on POSIX; restores the terminal attributes on the way out."""
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        first = os.read(fd, 1)
        if not first:
            return KEY_ESC
        char = first.decode('utf-8', 'replace')
        if char != '\x1b':
            return decode_key(char)
        # Esc may start a sequence; give the rest a short window to arrive.
        sequence = char
        for _ in range(2):
            ready, _w, _x = select.select([fd], [], [], _ESC_TIMEOUT)
            if not ready:
                break
            sequence += os.read(fd, 1).decode('utf-8', 'replace')
            if sequence in _SEQUENCES:
                return decode_key(sequence)
        return decode_key(sequence)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def _windows_getch() -> str:
    import msvcrt

    # getwch() exists on CPython/Windows (str); getch() is the documented
    # fallback and returns bytes, so every read is normalised to text.
    read = getattr(msvcrt, 'getwch', None) or getattr(msvcrt, 'getch', None)

    def next_char() -> str:
        if read is None:  # pragma: no cover - every CPython has getch
            raise RuntimeError('msvcrt exposes neither getwch nor getch')
        value = read()
        return value.decode('utf-8', 'replace') if isinstance(value, bytes) else str(value)

    char = next_char()
    if char in ('\x00', '\xe0'):          # arrow keys arrive as a two-char code
        return {'H': KEY_UP, 'P': KEY_DOWN}.get(next_char(), KEY_UNKNOWN)
    return char


def read_key() -> str:
    """Return the next key: a KEY_* constant, or the character itself."""
    if not interactive():
        line = sys.stdin.readline()
        if not line:
            return KEY_ESC
        return line.rstrip('\n')[:1] or KEY_ENTER
    raw = _windows_getch() if os.name == 'nt' else _posix_getch()
    return decode_key(raw)


def normalize(key: str) -> str:
    """Lower-case printable keys so `Q` and `q` behave the same."""
    if key in (KEY_UP, KEY_DOWN, KEY_ENTER, KEY_ESC, KEY_CTRL_C, KEY_UNKNOWN):
        return key
    return key.lower()
