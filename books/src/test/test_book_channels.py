#!/usr/bin/env python3
"""One action, one book, three channels: the same conclusion from each.

The CLI, the Web console and the TUI are three front ends over `core.actions`.
They may render differently, but they must agree on what happened and on which
book it happened to — that is what makes "pick a book" a property of the
session rather than of one channel.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http import server

import _fixture

TAGS = ('layer:infra', 'tier:fast')  # the three front ends over core.actions

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class ThreeChannelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = _fixture.build_book(os.path.join(cls.tmp.name, 'book-a'))
        cls.cli = _fixture.load_module(cls.root, 'cli')
        cls.tui = _fixture.load_module(cls.root, 'tui')
        cls.web = _fixture.load_module(cls.root, 'web')
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), cls.web.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def via_cli(self, action: str) -> tuple[int, str]:
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                code = self.cli.main([action])
        except SystemExit as exc:  # argparse reports an unknown action by exiting
            code = exc.code if isinstance(exc.code, int) else 1
        return code, buffer.getvalue()

    def via_tui(self, action: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.tui.main(['--once', action])
        return code, buffer.getvalue()

    def via_web(self, action: str) -> tuple[int, str]:
        import http.client
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        conn.request('POST', '/api/run', body=json.dumps({'action': action}).encode(),
                     headers={'Content-Type': 'application/json'})
        response = conn.getresponse()
        payload = json.loads(response.read())
        conn.close()
        return payload['code'], payload['output']

    def test_every_channel_reports_the_same_book(self):
        results = {
            'cli': self.via_cli('status'),
            'tui': self.via_tui('status'),
            'web': self.via_web('status'),
        }
        for channel, (code, text) in results.items():
            with self.subTest(channel=channel):
                self.assertEqual(code, 0, text[-400:])
                self.assertIn('测试之书', text)
                self.assertNotIn('Traceback', text)

    def test_every_channel_refuses_the_same_unknown_action(self):
        for channel, run in (('cli', self.via_cli), ('tui', self.via_tui),
                             ('web', self.via_web)):
            with self.subTest(channel=channel):
                code, text = run('no-such-action')
                self.assertNotEqual(code, 0, text[-200:])
                self.assertIn('no-such-action', text)

    def test_each_channel_works_on_the_book_it_was_started_for(self):
        other = os.path.join(self.tmp.name, 'book-b')
        _fixture.build_book(other)
        code, text = self.via_web('status')
        self.assertEqual(code, 0, text[-300:])
        self.assertEqual(os.path.abspath(self.web._config.current().root),
                         os.path.abspath(self.root))
        cli_code, cli_text = self.via_cli('status')
        self.assertEqual(cli_code, 0, cli_text[-300:])
        self.assertIn('测试之书', cli_text)


if __name__ == '__main__':
    unittest.main()
