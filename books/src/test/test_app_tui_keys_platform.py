#!/usr/bin/env python3
"""Platform key readers: POSIX cbreak path and the Windows msvcrt path."""

from __future__ import annotations

import importlib
import io
import sys
import types
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:app", "tier:fast")

_fixture.ensure_tools_path()

keys = importlib.import_module("app.keys")


class PosixReaderTest(unittest.TestCase):
    def run_reader(
        self, chunks: list[bytes], *, tty: bool = True, reads: list[bytes] | None = None
    ):
        """Drive _posix_getch with scripted os.read chunks and a fake fd."""
        stream = mock.Mock()
        stream.isatty.return_value = tty
        stream.fileno.return_value = 3
        feed = list(chunks)

        def fake_read(_fd, _n):
            if not feed:
                return b""
            chunk = feed.pop(0)
            if reads is not None:
                reads.append(chunk)
            return chunk

        termios = types.SimpleNamespace(
            tcgetattr=lambda fd: ["saved"], tcsetattr=lambda fd, when, saved: None, TCSADRAIN=0
        )
        tty_module = types.SimpleNamespace(setcbreak=lambda fd: None)
        # select reports readiness exactly when the script still has bytes queued
        select_module = types.SimpleNamespace(
            select=lambda r, w, x, timeout=None: ([3], [], []) if feed else ([], [], [])
        )
        with (
            mock.patch.object(keys.sys, "stdin", stream),
            mock.patch.object(keys.os, "read", side_effect=fake_read),
            mock.patch.dict(
                sys.modules, {"termios": termios, "tty": tty_module, "select": select_module}
            ),
        ):
            return keys._posix_getch()

    def test_printable_key_is_returned(self):
        self.assertEqual(self.run_reader([b"q"]), "q")

    def test_arrow_sequence_is_decoded(self):
        self.assertEqual(self.run_reader([b"\x1b", b"[", b"A"]), keys.KEY_UP)

    def test_enter_and_control_c(self):
        self.assertEqual(self.run_reader([b"\r"]), keys.KEY_ENTER)
        self.assertEqual(self.run_reader([b"\x03"]), keys.KEY_CTRL_C)

    def test_lone_escape_without_follow_up(self):
        self.assertEqual(self.run_reader([b"\x1b"]), keys.KEY_ESC)

    def test_empty_read_is_escape(self):
        self.assertEqual(self.run_reader([]), keys.KEY_ESC)

    def test_two_follow_up_bytes_completing_no_sequence_give_a_bare_escape(self):
        reads: list[bytes] = []
        key = self.run_reader([b"\x1b", b"[", b"Q", b"\x03"], reads=reads)
        self.assertEqual(key, keys.KEY_ESC)
        # the window is exactly two bytes: the escape plus two probes that never
        # spell a known sequence; the byte behind them waits for the next read
        self.assertEqual(reads, [b"\x1b", b"[", b"Q"])

    def test_terminal_attributes_are_restored(self):
        restored = []
        termios = types.SimpleNamespace(
            tcgetattr=lambda fd: ["saved"],
            tcsetattr=lambda fd, when, saved: restored.append(saved),
            TCSADRAIN=0,
        )
        stream = mock.Mock()
        stream.isatty.return_value = True
        stream.fileno.return_value = 3
        with (
            mock.patch.object(keys.sys, "stdin", stream),
            mock.patch.object(keys.os, "read", return_value=b"q"),
            mock.patch.dict(
                sys.modules,
                {"termios": termios, "tty": types.SimpleNamespace(setcbreak=lambda fd: None)},
            ),
        ):
            keys._posix_getch()
        self.assertEqual(restored, [["saved"]])

    def test_read_key_dispatches_to_posix_on_this_platform(self):
        with (
            mock.patch.object(keys, "interactive", return_value=True),
            mock.patch.object(keys, "_posix_getch", return_value="r"),
        ):
            self.assertEqual(keys.read_key(), "r")


class WindowsReaderTest(unittest.TestCase):
    def run_windows(self, chars: list[str]):
        feed = list(chars)
        msvcrt = types.SimpleNamespace(getwch=lambda: feed.pop(0) if feed else "")
        with mock.patch.dict(sys.modules, {"msvcrt": msvcrt}):
            return keys._windows_getch()

    def test_printable_key(self):
        self.assertEqual(self.run_windows(["x"]), "x")

    def test_arrow_prefix_is_mapped(self):
        self.assertEqual(self.run_windows(["\xe0", "H"]), keys.KEY_UP)
        self.assertEqual(self.run_windows(["\xe0", "P"]), keys.KEY_DOWN)

    def test_unknown_arrow_code_is_reported(self):
        self.assertEqual(self.run_windows(["\x00", "Z"]), keys.KEY_UNKNOWN)

    def test_bytes_from_getch_are_decoded(self):
        feed = [b"k"]
        msvcrt = types.SimpleNamespace(getch=lambda: feed.pop(0))
        with mock.patch.dict(sys.modules, {"msvcrt": msvcrt}):
            self.assertEqual(keys._windows_getch(), "k")


class LineModeTest(unittest.TestCase):
    def test_blank_line_is_treated_as_enter(self):
        with mock.patch.object(keys.sys, "stdin", io.StringIO("\n")):
            self.assertEqual(keys.read_key(), keys.KEY_ENTER)


if __name__ == "__main__":
    unittest.main()
