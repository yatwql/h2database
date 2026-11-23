#!/usr/bin/env python3
"""Print-grade PDF: chapter cover banners, TOC dot leaders, running header.

Steps, each independently callable (engine injectable, so tests need no browser):

  parse_headings(html)          H1-H4 with ids -> [{index, level, id, text}]
  inject_css(html)              add the @media print block before </head>
  render_pdf(html, pdf, engine) Chromium print with header/footer templates
  page_texts(pdf)               per-page text with whitespace collapsed
  add_outlines(pdf, headings)   write the PDF outline from the hdr markers
  build(html, pdf, engine)      run the four steps in order
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import contextlib
import os
import re
import subprocess
from typing import Any

from lib import _config, _errors, _fsutil, _mdutil

_fsutil.pin_stdout_utf8()

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..', '..'))
docs_dir = os.path.join(repo_root, 'books')
dist_dir = os.path.join(docs_dir, 'dist')
generate_script = os.path.join(script_dir, 'to_html.py')

CSS = 'PRINT_GRADE_CSS = """\n<style id="print-grade-css">\n@media print {\n    /* === H1 chapter cover === */\n    /* Each H1 starts on a fresh page with a large decorative banner. */\n    #content h1 {\n        page-break-before: always;\n        margin-top: 0;\n        padding-top: 100px;\n        font-size: 2.4em;\n        text-align: center;\n        border: none;\n        position: relative;\n    }\n    #content h1::before {\n        content: \'\';\n        display: block;\n        width: 100px;\n        height: 4px;\n        margin: 0 auto 30px;\n        background: linear-gradient(90deg, #1565C0, #4fc3f7);\n        border-radius: 2px;\n    }\n    #content h1::after {\n        content: \'\';\n        display: block;\n        width: 60%;\n        height: 1px;\n        margin: 30px auto 0;\n        background: #ddd;\n    }\n    /* Avoid orphan headings at page bottom. */\n    h2, h3, h4 { page-break-after: avoid; }\n    h2 { page-break-before: auto; }\n\n    /* === TOC dot leaders === */\n    /* Wraps each TOC entry so title and page number sit at flex extremes\n       with a dotted leader filling the gap between them. The page number\n       span is appended by ``to_pdf.py`` step 3 already; here we\n       only restyle the link container. */\n    #toc-page-nav a {\n        display: flex !important;\n        align-items: baseline;\n        gap: 6px;\n        padding: 3px 8px !important;\n        text-decoration: none;\n    }\n    #toc-page-nav a > span:not([style*="font-size:11px"]) {\n        flex: 1 1 auto;\n    }\n    /* The dotted leader is the pseudo-element between title text and\n       page number. Title and page sit at flex extremes; the leader\n       fills the middle with a string of dots truncated by overflow. */\n    #toc-page-nav a::after {\n        content: \'..............................................................\'\n                 \'..............................................................\';\n        flex: 1 0 auto;\n        margin: 0 4px;\n        overflow: hidden;\n        font-size: 12px;\n        letter-spacing: 1px;\n        color: #ccc;\n        white-space: nowrap;\n        order: 2;\n    }\n    #toc-page-nav a > span:last-child {\n        order: 3;\n        flex: 0 0 auto;\n        font-variant-numeric: tabular-nums;\n    }\n    #toc-page-nav a > div,\n    #toc-page-nav a > span:first-child {\n        order: 1;\n    }\n}\n</style>\n"""'


def parse_headings(html: str) -> list[dict]:
    """Heading records in document order (shared parser, see lib/_mdutil)."""
    return _mdutil.html_headings(html)


def inject_css(html: str) -> str:
    """Add the print-grade stylesheet once, just before </head>."""
    if 'id="print-grade-css"' in html:
        return html
    return html.replace('</head>', CSS + '</head>', 1)


def header_template(running_head: str, label: str) -> str:
    return (
        '<div style="font-size:9px;color:#666;width:100%;'
        'padding:4px 15mm;display:flex;justify-content:space-between;'
        'border-bottom:0.5px solid #ddd;">'
        f'<span>{running_head}</span>'
        f'<span style="color:#999;">{label}</span>'
        '</div>'
    )


def footer_template() -> str:
    return (
        '<div style="font-size:9px;color:#666;width:100%;'
        'padding:6px 15mm;text-align:center;'
        'border-top:0.5px solid #ddd;">'
        '第 <span class="pageNumber"></span> 页 / 共 '
        '<span class="totalPages"></span> 页'
        '</div>'
    )


def render_pdf(html_path: str, pdf_path: str, engine: Any = None,
               running_head: str = '', label: str = '') -> None:
    """Print ``html_path`` to ``pdf_path`` with Chromium."""
    if engine is None:
        from playwright.sync_api import sync_playwright as engine
    with engine() as p:
        browser = p.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = browser.new_page()
        page.goto('file:///' + str(html_path).replace('\\', '/'),
                  wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
        page.evaluate("""() => {
            const content = document.getElementById('content');
            if (!content) return;
            const m = document.createElement('span');
            m.className = 'content-marker';
            m.textContent = '__CONTENT__';
            m.style.cssText = 'display:inline;font-size:3px;color:#ffffff;';
            content.insertBefore(m, content.firstChild);
        }""")
        page.evaluate("""() => {
            const content = document.getElementById('content');
            if (!content) return;
            const els = content.querySelectorAll('h1[id], h2[id], h3[id], h4[id]');
            els.forEach((h, i) => {
                const m = document.createElement('span');
                m.className = 'hdr-marker';
                m.textContent = '__hdr_' + i + '__';
                m.style.cssText = 'display:inline;font-size:3px;color:#ffffff;';
                h.parentNode.insertBefore(m, h);
            });
        }""")
        scale = float(_config.THRESHOLDS.get('print_scale', 1.0) or 1.0)
        page.pdf(
            path=pdf_path,
            format='A4',
            scale=scale,
            margin={'top': '20mm', 'bottom': '25mm', 'left': '15mm', 'right': '15mm'},
            print_background=True,
            display_header_footer=False,
            header_template=header_template(running_head, label),
            footer_template=footer_template(),
            prefer_css_page_size=False,
        )
        browser.close()


def page_texts(pdf_path: str) -> list[str]:
    from pypdf import PdfReader
    return [re.sub(r'\s+', '', page.extract_text() or '')
            for page in PdfReader(pdf_path).pages]


def content_start(texts: list[str]) -> int:
    """Page index of the __CONTENT__ marker (0 when absent)."""
    for index, text in enumerate(texts):
        if '__CONTENT__' in text:
            return index
    return 0


def add_outlines(pdf_path: str, headings: list[dict]) -> tuple[int, list[str]]:
    """Write the outline; returns (entries added, heading titles not found)."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    texts = [re.sub(r'\s+', '', page.extract_text() or '') for page in reader.pages]

    stack: dict[int, Any] = {}
    found = 0
    missing: list[str] = []
    cursor = content_start(texts)
    for heading in headings:
        marker = f"__hdr_{heading['index']}__"
        page_number = None
        for index in range(cursor, len(texts)):
            if marker in texts[index]:
                page_number = index
                break
        if page_number is None:
            missing.append(heading['text'])
            continue
        cursor = page_number
        parent: Any = None
        for level in range(heading['level'] - 1, 0, -1):
            if level in stack:
                parent = stack[level]
                break
        stack[heading['level']] = writer.add_outline_item(
            title=heading['text'], page_number=page_number, parent=parent)
        found += 1
    writer.write(pdf_path)
    return found, missing


def build(html_path: str | None = None, pdf_path: str | None = None,
          engine: Any = None) -> tuple[int, list[str]]:
    """Full print-grade pipeline over the given paths (book defaults)."""
    html_source = html_path or _config.merged_html()
    target = pdf_path or _config.merged_print_pdf()
    html = _fsutil.read_text(html_source)
    headings = parse_headings(html)
    print(f'  Parsed {len(headings)} headings from HTML')

    staging = _config.dist(f'_{ _config.MERGED_NAME }-print.html')
    _fsutil.write_text(staging, inject_css(html))
    try:
        render_pdf(staging, target, engine=engine,
                   running_head=_config.project('running_head', 'book'),
                   label=f'印刷版 v{_config.VERSION}')
        print(f'  Rendered: {target}')
    finally:
        with contextlib.suppress(OSError):
            os.remove(staging)

    found, missing = add_outlines(target, headings)
    print(f'  Created {found} / {len(headings)} PDF outline entries')
    for title in missing[:5]:
        print(f'    - {title[:60]}')
    return found, missing


def main(argv: list[str] | None = None, engine: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--html', help='source HTML (default: merged HTML)')
    parser.add_argument('--pdf', help='target PDF (default: print-grade PDF)')
    parser.add_argument('--skip-html', action='store_true',
                        help='do not regenerate the HTML before printing')
    args = parser.parse_args(argv)

    if not args.skip_html and os.path.exists(generate_script):
        result = subprocess.run([_sys.executable, generate_script],
                                capture_output=True, text=True, encoding='utf-8',
                                cwd=repo_root, check=False)
        print(result.stdout)
        if result.returncode != 0:
            print('HTML generation FAILED:', result.stderr, file=_sys.stderr)
            return 1
    try:
        build(args.html, args.pdf, engine)
    except Exception as exc:  # noqa: BLE001 - report, do not dump a traceback
        print(f'  print-grade PDF FAILED: {exc}', file=_sys.stderr)
        return 1
    print(f'Print-grade PDF: {args.pdf or _config.merged_print_pdf()}')
    return 0


if __name__ == '__main__':
    _sys.exit(_errors.run(main, _sys.argv[1:]))
