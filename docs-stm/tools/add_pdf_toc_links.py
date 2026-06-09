#!/usr/bin/env python3
"""Add clickable printed-TOC links to the generated PDF.

The mapping is positional, not title-based, so duplicate heading titles are safe.
Each HTML TOC entry is mapped to the corresponding PDF outline entry by order.
Annotations are distributed across the printed TOC pages using absolute browser
coordinates and A4 page geometry.
"""
from __future__ import annotations

from pathlib import Path
import os

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.generic import NameObject, TextStringObject

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DOCS_DIR = REPO_ROOT / 'docs-stm'
HTML_PATH = DOCS_DIR / 'h2-source-code-analysis.html'
PDF_PATH = DOCS_DIR / 'h2-source-code-analysis.pdf'
TMP_PATH = PDF_PATH.with_suffix('.pdf.tmp')
VIEWPORT_WIDTH = 794.0
VIEWPORT_HEIGHT = 1123.0


def collect_outline(reader: PdfReader) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []

    def walk(items) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            title = str(item.get('/Title', '')).strip()
            if not title:
                continue
            page_num = reader.get_destination_page_number(item)
            entries.append((title, page_num))

    walk(reader.outline)
    return entries


def get_toc_links() -> list[dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = browser.new_page(viewport={'width': int(VIEWPORT_WIDTH), 'height': int(VIEWPORT_HEIGHT)})
        page.goto('file:///' + str(HTML_PATH).replace('\\', '/'), wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
        links = page.evaluate("""() => {
            const nav = document.getElementById('toc-page-nav');
            if (!nav) return [];
            return Array.from(nav.querySelectorAll('a')).map((a, index) => {
                const r = a.getBoundingClientRect();
                return {
                    index,
                    text: a.textContent.trim(),
                    href: a.getAttribute('href') || '',
                    rect: {
                        x: r.x + window.scrollX,
                        y: r.y + window.scrollY,
                        w: r.width,
                        h: r.height,
                    },
                };
            });
        }""")
        browser.close()
        return links


def add_links() -> None:
    toc_links = get_toc_links()
    print(f'TOC links in HTML: {len(toc_links)}')

    reader = PdfReader(str(PDF_PATH))
    outline_entries = collect_outline(reader)
    print(f'Outline entries in PDF: {len(outline_entries)}')

    if len(toc_links) > len(outline_entries):
        raise RuntimeError(f'TOC ({len(toc_links)}) exceeds outline entries ({len(outline_entries)})')
    if toc_links and outline_entries:
        first_link = toc_links[0]['text']
        first_outline = outline_entries[0][0]
        if first_link != first_outline:
            print(f'  Note: first TOC entry "{first_link[:40]}" != first outline "{first_outline[:40]}"')

    print(f'TOC links to add: {len(toc_links)} / {len(outline_entries)} outline entries')

    writer = PdfWriter()
    # Use append() which preserves outlines (clone_document_from_reader may lose them)
    writer.append(reader)

    page_width = float(reader.pages[0].mediabox.width)
    page_height = float(reader.pages[0].mediabox.height)

    added = 0
    for link, (_, target_page) in zip(toc_links, outline_entries):
        rect = link['rect']
        center_y = rect['y'] + rect['h'] / 2
        page_number = int(center_y // VIEWPORT_HEIGHT)
        y_on_page = rect['y'] - page_number * VIEWPORT_HEIGHT
        if page_number >= len(reader.pages):
            raise RuntimeError(f'TOC link outside PDF page range: {link["text"][:80]} -> page {page_number + 1}')

        x0 = rect['x'] * page_width / VIEWPORT_WIDTH
        x1 = (rect['x'] + rect['w']) * page_width / VIEWPORT_WIDTH
        y0 = page_height - (y_on_page + rect['h']) * page_height / VIEWPORT_HEIGHT
        y1 = page_height - y_on_page * page_height / VIEWPORT_HEIGHT

        # Links near a printed page boundary can straddle the edge by a few
        # points because browser CSS pixels and PDF points are rounded
        # differently. Clamp to the page box; the center-page assignment above
        # keeps the annotation on the visible page.
        x0 = max(0.0, min(x0, page_width))
        x1 = max(0.0, min(x1, page_width))
        y0 = max(0.0, min(y0, page_height))
        y1 = max(0.0, min(y1, page_height))
        if not (x0 < x1 and y0 < y1):
            raise RuntimeError(f'Invalid TOC link rectangle for {link["text"][:80]}: {(x0, y0, x1, y1)}')

        annotation = Link(
            rect=(x0, y0, x1, y1),
            target_page_index=target_page,
            border=[0, 0, 0],
        )
        annotation[NameObject('/NM')] = TextStringObject(f'toc-link-{link["index"]}')
        writer.add_annotation(page_number, annotation)
        added += 1

    writer.write(str(TMP_PATH))
    # Validate the temporary file is readable before replacing the original.
    PdfReader(str(TMP_PATH))
    os.replace(TMP_PATH, PDF_PATH)
    print(f'TOC links added: {added}')


if __name__ == '__main__':
    add_links()
