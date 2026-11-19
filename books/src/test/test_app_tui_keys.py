#!/usr/bin/env python3
"""Key decoding: one press per event, arrows recognised, line mode for pipes."""
from __future__ import annotations

import importlib
import io
import unittest
from unittest import mock

import _fixture

_fixture.ensure_tools_path()

keys = importlib.import_module('app.keys')


class KeyDecodingTest(unittest.TestCase):
    def test_arrow_sequences_map_to_up_and_down(self):
        self.assertEqual(keys.decode_key('\x1b[A'), keys.KEY_UP)
        self.assertEqual(keys.decode_key('\x1b[B'), keys.KEY_DOWN)

    def test_application_cursor_mode_arrows_are_equivalent(self):
        self.assertEqual(keys.decode_key('\x1bOA'), keys.KEY_UP)
        self.assertEqual(keys.decode_key('\x1bOB'), keys.KEY_DOWN)

    def test_enter_accepts_carriage_return_and_newline(self):
        self.assertEqual(keys.decode_key('\r'), keys.KEY_ENTER)
        self.assertEqual(keys.decode_key('\n'), keys.KEY_ENTER)

    def test_control_c_is_its_own_key(self):
        self.assertEqual(keys.decode_key('\x03'), keys.KEY_CTRL_C)

    def test_printable_keys_are_returned_as_themselves(self):
        self.assertEqual(keys.decode_key('4'), '4')
        self.assertEqual(keys.decode_key('q'), 'q')

    def test_lone_escape_cancels(self):
        self.assertEqual(keys.decode_key('\x1b'), keys.KEY_ESC)

    def test_unknown_escape_sequence_does_not_leak_a_letter(self):
        self.assertEqual(keys.decode_key('\x1b[C'), keys.KEY_ESC)

    def test_normalize_lowercases_printables_only(self):
        self.assertEqual(keys.normalize('Q'), 'q')
        self.assertEqual(keys.normalize(keys.KEY_UP), keys.KEY_UP)
        self.assertEqual(keys.normalize(keys.KEY_ENTER), keys.KEY_ENTER)


class PipedInputTest(unittest.TestCase):
    def test_line_mode_returns_the_first_character(self):
        with mock.patch.object(keys.sys, 'stdin', io.StringIO('q\n')):
            self.assertEqual(keys.read_key(), 'q')

    def test_end_of_input_cancels(self):
        with mock.patch.object(keys.sys, 'stdin', io.StringIO('')):
            self.assertEqual(keys.read_key(), keys.KEY_ESC)

    def test_interactive_detection_survives_a_closed_stdin(self):
        broken = mock.Mock()
        broken.isatty.side_effect = ValueError('closed')
        with mock.patch.object(keys.sys, 'stdin', broken):
            self.assertFalse(keys.interactive())


if __name__ == '__main__':
    unittest.main()
