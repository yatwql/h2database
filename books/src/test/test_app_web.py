#!/usr/bin/env python3
"""The Web console: the page, the JSON API and the bind/shutdown path."""

from __future__ import annotations

import http.client
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock
from contextlib import redirect_stdout
from http import server

import _fixture

TAGS = ('layer:app', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

class WebConsoleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = _fixture.build_book(cls.tmp.name)
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

    def url(self, path: str) -> str:
        return f'http://127.0.0.1:{self.port}{path}'

    def request(self, method: str, path: str, body: bytes | None = None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        headers = {'Content-Type': 'application/json'} if body is not None else {}
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        status = response.status
        conn.close()
        return status, payload

    def get(self, path: str):
        return self.request('GET', path)

    def post(self, path: str, body: bytes):
        return self.request('POST', path, body)

    def test_index_renders_actions_and_app_title(self):
        status, payload = self.get('/')
        html = payload.decode('utf-8')
        self.assertEqual(status, 200)
        self.assertIn('bookwright', html)
        self.assertIn('status', html)

    def test_index_alias_serves_same_page(self):
        status, _payload = self.get('/index.html')
        self.assertEqual(status, 200)

    def test_status_endpoint_returns_json(self):
        _status, raw = self.get('/api/status')
        payload = json.loads(raw)
        self.assertIn('code', payload)
        self.assertIn('output', payload)

    def test_unknown_get_is_404(self):
        status, _payload = self.get('/nope')
        self.assertEqual(status, 404)

    def test_post_runs_action(self):
        _status, raw = self.post('/api/run', json.dumps({'action': 'status'}).encode())
        payload = json.loads(raw)
        self.assertEqual(payload['code'], 0)

    def test_post_llm_ask_passes_prompt(self):
        _status, raw = self.post('/api/run',
                                 json.dumps({'action': 'llm-ask',
                                             'prompt': '你好'}).encode())
        payload = json.loads(raw)
        self.assertIn(payload['code'], (0, 1, 2))

    def test_an_action_that_raises_answers_with_a_code(self):
        def boom(*_args, **_kwargs):
            raise RuntimeError('no provider')

        with mock.patch.object(self.web.actions, 'run', side_effect=boom):
            status, raw = self.post('/api/run', json.dumps({'action': 'status'}).encode())
        payload = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(payload['code'], 1)
        self.assertIn('no provider', payload['output'])

    def test_post_invalid_json_is_400(self):
        status, _payload = self.post('/api/run', b'{not json')
        self.assertEqual(status, 400)

    def test_post_unknown_path_is_404(self):
        status, _payload = self.post('/api/other', b'{}')
        self.assertEqual(status, 404)

    def test_main_binds_and_exits_on_interrupt(self):
        buffer = io.StringIO()
        calls = []

        class FakeServer:
            def __init__(self, address, handler):
                calls.append(address)

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                calls.append('closed')

        original = self.web.server.ThreadingHTTPServer
        self.web.server.ThreadingHTTPServer = FakeServer
        try:
            with redirect_stdout(buffer):
                code = self.web.main(['--port', '9999'])
        finally:
            self.web.server.ThreadingHTTPServer = original
        self.assertEqual(code, 0)
        self.assertEqual(calls[0], ('127.0.0.1', 9999))
        self.assertIn('bye', buffer.getvalue())

if __name__ == '__main__':
    unittest.main()
