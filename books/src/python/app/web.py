#!/usr/bin/env python3
"""Web entry point: a single page plus a JSON API over the shared actions.

  python app/web.py --port 8080

Routes:
  GET  /            minimal HTML console (buttons per action)
  GET  /api/status  JSON: book + LLM status
  POST /api/run     JSON {"action": "...", "prompt": "..."} -> {"code", "output"}

Binds to 127.0.0.1 by default: the actions write to the repository.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http import server

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import actions
from lib import _config, _fsutil

_fsutil.pin_stdout_utf8()

PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>__APP__</title>
<style>body{font-family:system-ui;margin:2rem;max-width:52rem}
button{margin:.2rem;padding:.4rem .8rem}pre{background:#f5f5f5;padding:1rem;
white-space:pre-wrap}</style></head>
<body><h1>__APP__</h1>
<p><label>书 <select id="book"></select></label>
<label>版本 <select id="edition"><option value="">main</option></select></label>
<span id="where"></span></p>
<p id="actions"></p>
<p><input id="prompt" size="50" placeholder="llm-ask 的提示词">
<button onclick="run('llm-ask')">llm-ask</button></p>
<pre id="out">就绪</pre>
<script>
const ACTIONS = __ACTIONS__;
document.getElementById('actions').innerHTML = Object.entries(ACTIONS)
  .map(([name, desc]) => `<button title="${desc}" onclick="run('${name}')">${name}</button>`)
  .join('');
async function loadBooks() {
  const data = await (await fetch('/api/books')).json();
  const book = document.getElementById('book');
  book.innerHTML = data.books.map(item =>
    `<option value="${item.root}"${item.root === data.current ? ' selected' : ''}>` +
    `${item.title || item.root}${item.edition ? ' · ' + item.edition : ''}</option>`).join('');
  document.getElementById('where').textContent =
    data.current ? `工作目录：${data.current}` : '';
}
loadBooks();
async function run(action) {
  const out = document.getElementById('out');
  out.textContent = `运行 ${action} …`;
  const response = await fetch('/api/run', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action, prompt: document.getElementById('prompt').value,
      book: document.getElementById('book').value,
      edition: document.getElementById('edition').value})});
  const data = await response.json();
  out.textContent = `[退出码 ${data.code}]\\n${data.output}`;
}
</script></body></html>
"""


def book_choices() -> dict:
    """Books this console can work on, plus the one it started with."""
    active = _config.current().root
    books = []
    for root in _config.candidate_books(active):
        entry = {'root': root, 'title': '', 'version': '',
                 'config': os.path.basename(os.path.dirname(
                     os.path.join(root, 'data', 'book')))}
        try:
            cfg = _config.Config(root)
            entry.update({'title': cfg.title, 'version': cfg.version,
                          'config': os.path.basename(root)})
        except _config.ConfigError:
            pass
        books.append(entry)
    return {'current': active, 'books': books}


class Handler(server.BaseHTTPRequestHandler):
    """Serve the console page and the JSON API."""

    def _send(self, code: int, body: str, content_type: str) -> None:
        payload = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path in ('/', '/index.html'):
            page = (PAGE.replace('__ACTIONS__', json.dumps(actions.ACTIONS, ensure_ascii=False))
                    .replace('__APP__', _config.app_title()))
            self._send(200, page, 'text/html; charset=utf-8')
        elif self.path == '/api/books':
            self._send(200, json.dumps(book_choices(), ensure_ascii=False),
                       'application/json; charset=utf-8')
        elif self.path == '/api/status':
            code, text = actions.run('status')
            self._send(200, json.dumps({'code': code, 'output': text}, ensure_ascii=False),
                       'application/json; charset=utf-8')
        else:
            self._send(404, 'not found', 'text/plain; charset=utf-8')

    def do_POST(self) -> None:
        if self.path != '/api/run':
            self._send(404, 'not found', 'text/plain; charset=utf-8')
            return
        length = int(self.headers.get('Content-Length') or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b'{}')
        except json.JSONDecodeError:
            self._send(400, json.dumps({'code': 2, 'output': 'invalid JSON'}),
                       'application/json; charset=utf-8')
            return
        action = str(payload.get('action', ''))
        book = str(payload.get('book', '') or '')
        if book and not os.path.isfile(os.path.join(book, 'data', 'book', 'book.toml')):
            self._send(400, json.dumps({'code': 2, 'output': f'没有找到 book.toml：{book}'},
                                       ensure_ascii=False),
                       'application/json; charset=utf-8')
            return
        if action == 'llm-ask':
            kwargs = {'prompt': str(payload.get('prompt', ''))}
        elif action in actions.ANALYZE_ACTIONS:
            kwargs = {'refresh': bool(payload.get('refresh')),
                      'force': bool(payload.get('force'))}
        else:
            kwargs = {}
        try:
            code, text = actions.run(action, book=book,
                                     edition=str(payload.get('edition', '') or ''), **kwargs)
        except Exception as exc:  # noqa: BLE001 - the page relays failures, it does not raise
            code, text = 1, f'{type(exc).__name__}: {exc}'
        self._send(200, json.dumps({'code': code, 'output': text}, ensure_ascii=False),
                   'application/json; charset=utf-8')

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write('%s\n' % (format % args))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--book', default='', help='book root to serve')
    parser.add_argument('--edition', default='', help='manuscript edition to serve')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)

    httpd = server.ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'books toolchain on http://{args.host}:{args.port} (Ctrl+C 退出)')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nbye')
    finally:
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
