#!/usr/bin/env python3
"""Generate the PDF from the existing HTML (no HTML rebuild).

The work is split into steps that can be exercised without a browser:

  parse_headings(html)                HTML H1-H4 with ids -> (level, text, id)
  render_pdf(html, pdf, engine=None)  Chromium print, returns marker headings
  page_texts(pdf)                     per-page text with whitespace collapsed
  content_start(page_texts, keys)     first body page (skips cover/TOC)
  build_outline(writer, texts, keys)  outline entries for the PDF
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import os
import re
from typing import Any

from lib import _config, _errors, _fsutil, _mdutil
from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

_fsutil.pin_stdout_utf8()

script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = _config.MANUSCRIPT_DIR
html_path = _config.merged_html()
pdf_path = _config.merged_pdf()

MARKER_MIN_LEN = 3
FALLBACK_MIN_LEN = 5


def plain(text: str) -> str:
    """Strip inline tags and the zero-width space the renderer inserts."""
    return _mdutil.plain_text(text)


def parse_headings(html: str) -> list[tuple[int, str, str]]:
    """Return (level, plain text, anchor id) for every H1-H4 with an id."""
    return [(item["level"], item["text"], item["id"]) for item in _mdutil.html_headings(html)]


def render_pdf(html: str, target: str, engine: Any = None) -> list[dict]:
    """Print ``html`` to ``target`` with Chromium, returning heading markers."""
    engine = engine or sync_playwright
    with engine() as p:
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = browser.new_page()
        page.goto(
            "file:///" + str(html).replace("\\", "/"), wait_until="networkidle", timeout=60000
        )
        page.wait_for_timeout(3000)
        page.evaluate("""() => {
            const content = document.getElementById('content');
            if (!content) return;
            const marker = document.createElement('span');
            marker.className = 'content-marker';
            marker.textContent = '__CONTENT__';
            marker.style.cssText = 'display:inline;font-size:0.1px;color:transparent;';
            content.insertBefore(marker, content.firstChild);
        }""")
        headings = page.evaluate("""() => {
            const content = document.getElementById('content');
            if (!content) return [];
            const els = content.querySelectorAll('h1[id], h2[id], h3[id], h4[id]');
            const result = [];
            els.forEach((h, i) => {
                const marker = document.createElement('span');
                marker.className = 'hdr-marker';
                marker.textContent = '__hdr_' + i + '__';
                marker.style.cssText = 'display:inline;font-size:0.1px;color:transparent;';
                h.parentNode.insertBefore(marker, h);
                result.push({index: i, id: h.id, text: h.textContent.trim(),
                             level: parseInt(h.tagName.substring(1))});
            });
            return result;
        }""")
        page.pdf(
            path=target,
            format="A4",
            margin={"top": "20mm", "bottom": "25mm", "left": "15mm", "right": "15mm"},
            print_background=True,
            display_header_footer=False,
            prefer_css_page_size=False,
        )
        browser.close()
    return headings or []


def page_texts(pdf: str) -> list[str]:
    """Per-page text with all whitespace removed (markers stay intact)."""
    return [re.sub(r"\s+", "", page.extract_text() or "") for page in PdfReader(pdf).pages]


def content_start(texts: list[str], search_keys: list[tuple[int, str, str]]) -> int:
    """First page that belongs to the body (after cover and printed TOC)."""
    for index, text in enumerate(texts):
        if "__content__" in text:
            return index
    sample = [key[2] for key in search_keys[:30]]
    counts = [sum(1 for key in sample if key in text) for text in texts]
    for index, count in enumerate(counts):
        if index > 0 and counts[index - 1] >= 10 and count < 10:
            return index
    return min(2, len(texts))


def build_outline(
    writer: PdfWriter, texts: list[str], search_keys: list[tuple[int, str, str]], start: int = 0
) -> tuple[int, list[str]]:
    """Add outline entries; returns (added, titles not found)."""
    stack: dict[int, Any] = {}
    added = 0
    missing: list[str] = []
    current = start
    for level, text, key in search_keys:
        page_number = None
        for index in range(current, len(texts)):
            if len(key) >= MARKER_MIN_LEN and key in texts[index]:
                page_number = index
                break
        if page_number is None and len(key) >= FALLBACK_MIN_LEN:
            short = key[:20]
            for index in range(current, len(texts)):
                if short in texts[index]:
                    page_number = index
                    break
        if page_number is None:
            missing.append(text)
            continue
        current = page_number
        parent: Any = None
        for level_up in range(level - 1, 0, -1):
            if level_up in stack:
                parent = stack[level_up]
                break
        stack[level] = writer.add_outline_item(title=text, page_number=page_number, parent=parent)
        added += 1
    return added, missing


def build(
    html_path: str = html_path, pdf_path: str = pdf_path, engine: Any = None
) -> tuple[int, list[str]]:
    """Full pipeline: parse headings, print, index pages, write the outline."""
    _fsutil.ensure_dir(pdf_path)
    headings = parse_headings(_fsutil.read_text(html_path))
    print(f"Parsed {len(headings)} headings from HTML")

    markers = render_pdf(html_path, pdf_path, engine)
    print("PDF rendered")

    texts = page_texts(pdf_path)
    marker_ok = any("__hdr_0__" in text for text in texts)
    print(f"Markers in PDF: {marker_ok}")
    if marker_ok:
        search_keys = [
            (item["level"], item["text"], "__hdr_{}__".format(item["index"])) for item in markers
        ]
    else:
        print("Markers not found, falling back to text matching")
        search_keys = [(level, text, re.sub(r"\s+", "", text)) for level, text, _id in headings]

    writer = PdfWriter()
    for page in PdfReader(pdf_path).pages:
        writer.add_page(page)

    start = content_start(texts, search_keys)
    if not marker_ok:
        print(f"Content start: page {start}")
    added, missing = build_outline(writer, texts, search_keys, start)

    print(f"Outlines: {added} / {len(search_keys)}")
    if missing:
        print(f"Not found ({len(missing)}):")
        for title in missing[:5]:
            print(f"  - {title[:60]}")

    writer.write(pdf_path)
    print("PDF saved")
    return added, missing


def main(argv: list[str] | None = None, engine: Any = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--html", default=html_path, help="source HTML")
    parser.add_argument("--pdf", default=pdf_path, help="target PDF")
    args = parser.parse_args(argv)
    try:
        build(args.html, args.pdf, engine)
    except Exception as exc:
        print(
            f"error: chromium unavailable ({exc}); run: python -m playwright install chromium",
            file=_sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    _sys.exit(_errors.run(main, _sys.argv[1:]))
