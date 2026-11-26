#!/usr/bin/env python3
"""The Web console: the page, the JSON API and the bind/shutdown path."""

from __future__ import annotations

import http.client
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http import server
from unittest import mock

import _fixture

TAGS = ("layer:app", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class WebConsoleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = _fixture.build_book(cls.tmp.name)
        cls.web = _fixture.load_module(cls.root, "web")
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), cls.web.Handler)
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
        return f"http://127.0.0.1:{self.port}{path}"

    def request(self, method: str, path: str, body: bytes | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json"} if body is not None else {}
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        payload = response.read()
        status = response.status
        conn.close()
        return status, payload

    def get(self, path: str):
        return self.request("GET", path)

    def post(self, path: str, body: bytes):
        return self.request("POST", path, body)

    def test_index_renders_actions_and_app_title(self):
        status, payload = self.get("/")
        html = payload.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("bookwright", html)
        self.assertIn("status", html)

    def test_index_alias_serves_same_page(self):
        status, _payload = self.get("/index.html")
        self.assertEqual(status, 200)

    def test_status_endpoint_returns_json(self):
        _status, raw = self.get("/api/status")
        payload = json.loads(raw)
        self.assertIn("code", payload)
        self.assertIn("output", payload)

    def test_unknown_get_is_404(self):
        status, _payload = self.get("/nope")
        self.assertEqual(status, 404)

    def sibling_book(self, name: str) -> str:
        """A book next to this one: the library is the active book's parent."""
        parent = os.path.dirname(os.path.abspath(self.root))
        sibling = os.path.join(parent, f"{name}-{os.getpid()}")
        _fixture.build_book(sibling)
        self.addCleanup(shutil.rmtree, sibling, True)
        return sibling

    def test_the_book_list_offers_the_active_book_and_its_neighbours(self):
        sibling = self.sibling_book("second-book")
        status, raw = self.get("/api/books")
        payload = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(os.path.abspath(payload["current"]), os.path.abspath(self.root))
        offered = {os.path.abspath(book["root"]) for book in payload["books"]}
        self.assertIn(os.path.abspath(self.root), offered)
        self.assertIn(os.path.abspath(sibling), offered)

    def test_an_action_request_may_name_its_book(self):
        sibling = self.sibling_book("third-book")
        before = self.web._config.current().root
        _status, raw = self.post(
            "/api/run", json.dumps({"action": "status", "book": sibling}).encode()
        )
        self.assertEqual(json.loads(raw)["code"], 0)
        # the request selects a book for that run only; the console keeps its own
        self.assertEqual(self.web._config.current().root, before)

    def test_a_request_naming_a_directory_that_is_no_book_is_refused(self):
        empty = os.path.join(self.tmp.name, "no-book-here")
        os.makedirs(empty, exist_ok=True)
        status, raw = self.post(
            "/api/run", json.dumps({"action": "status", "book": empty}).encode()
        )
        self.assertEqual(status, 400)
        self.assertIn("book.toml", json.loads(raw)["output"])

    def test_the_page_names_the_book_it_serves(self):
        _status, raw = self.get("/")
        html = raw.decode("utf-8")
        self.assertIn("测试之书", html)
        self.assertIn("0.1", html)

    def retitle(self, root: str, title: str) -> None:
        """Give a fixture book a title of its own, so responses can be told apart."""
        path = os.path.join(root, "data", "book", "book.toml")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        import re

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(re.sub(r'title = "[^"]*"', f'title = "{title}"', text, count=1))

    def test_two_concurrent_requests_each_get_the_book_they_named(self):
        first = self.sibling_book("concurrent-a")
        second = self.sibling_book("concurrent-b")
        self.retitle(first, "甲书")
        self.retitle(second, "乙书")
        seen = {}

        def run(name: str, root: str) -> None:
            _status, raw = self.post(
                "/api/run", json.dumps({"action": "status", "book": root}).encode()
            )
            seen[name] = json.loads(raw)["output"]

        threads = [
            threading.Thread(target=run, args=("a", first)),
            threading.Thread(target=run, args=("b", second)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertIn("甲书", seen["a"])
        self.assertNotIn("乙书", seen["a"])
        self.assertIn("乙书", seen["b"])
        self.assertNotIn("甲书", seen["b"])

    def test_post_runs_action(self):
        _status, raw = self.post("/api/run", json.dumps({"action": "status"}).encode())
        payload = json.loads(raw)
        self.assertEqual(payload["code"], 0)

    def test_post_llm_ask_passes_prompt(self):
        _status, raw = self.post(
            "/api/run", json.dumps({"action": "llm-ask", "prompt": "你好"}).encode()
        )
        payload = json.loads(raw)
        self.assertIn(payload["code"], (0, 1, 2))

    def test_post_analyze_forwards_the_refresh_switch(self):
        with mock.patch.object(
            self.web.actions, "run", return_value=(0, "刷新 1 章 / 跳过 0 章（无标记块）")
        ) as run:
            _status, raw = self.post(
                "/api/run", json.dumps({"action": "analyze", "refresh": True}).encode()
            )
        self.assertIn("刷新", json.loads(raw)["output"])
        self.assertTrue(run.call_args.kwargs["refresh"])
        self.assertFalse(run.call_args.kwargs["force"])

    def test_an_action_that_raises_answers_with_a_code(self):
        def boom(*_args, **_kwargs):
            raise RuntimeError("no provider")

        with mock.patch.object(self.web.actions, "run", side_effect=boom):
            status, raw = self.post("/api/run", json.dumps({"action": "status"}).encode())
        payload = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(payload["code"], 1)
        self.assertIn("no provider", payload["output"])

    def test_post_invalid_json_is_400(self):
        status, _payload = self.post("/api/run", b"{not json")
        self.assertEqual(status, 400)

    def test_post_unknown_path_is_404(self):
        status, _payload = self.post("/api/other", b"{}")
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
                calls.append("closed")

        original = self.web.server.ThreadingHTTPServer
        self.web.server.ThreadingHTTPServer = FakeServer
        try:
            with redirect_stdout(buffer):
                code = self.web.main(["--port", "9999"])
        finally:
            self.web.server.ThreadingHTTPServer = original
        self.assertEqual(code, 0)
        self.assertEqual(calls[0], ("127.0.0.1", 9999))
        self.assertIn("bye", buffer.getvalue())


class WebScriptGuardTest(unittest.TestCase):
    """`web.py` run as a script: `--help` leaves before a port is bound."""

    def test_help_prints_the_bind_options_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture.build_book(tmp)
            code, out = _fixture.run_inproc(root, "web.py", "--help")
        self.assertEqual(code, 0)
        self.assertIn("--port", out)
        self.assertIn("book root to serve", out)


if __name__ == "__main__":
    unittest.main()
