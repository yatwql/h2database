#!/usr/bin/env python3
"""Add clickable printed-TOC links to the generated PDF.

The mapping is positional, not title-based, so duplicate heading titles are safe.
Each HTML TOC entry is mapped to the corresponding PDF outline entry by order.
Annotations are distributed across the printed TOC pages using absolute browser
coordinates and A4 page geometry.
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
from pathlib import Path
from typing import Any

from lib import _browser, _config, _errors
from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.generic import ArrayObject, NameObject, TextStringObject

SCRIPT_DIR = Path(__file__).resolve().parent
VIEWPORT_WIDTH = 794.0
VIEWPORT_HEIGHT = 1123.0


def collect_outline(reader: PdfReader) -> list[tuple[str, int]]:
    entries: list[tuple[str, Any]] = []

    def walk(items) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            title = str(item.get("/Title", "")).strip()
            if not title:
                continue
            page_num = reader.get_destination_page_number(item)
            entries.append((title, page_num))

    walk(reader.outline)
    return entries


def get_toc_links(html_path: Path | None = None) -> list[dict]:
    html_path = Path(html_path) if html_path else Path(_config.merged_html())
    with sync_playwright() as p:
        browser = _browser.launch(p)
        page = browser.new_page(
            viewport={"width": int(VIEWPORT_WIDTH), "height": int(VIEWPORT_HEIGHT)}
        )
        page.goto(
            "file:///" + str(html_path).replace("\\", "/"), wait_until="networkidle", timeout=60000
        )
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


def _require_inputs(html_path: Path, pdf_path: Path) -> None:
    """Both inputs must exist: the message says which step to run first."""
    if not html_path.exists():
        raise _errors.ToolError(f"error: HTML not found: {html_path} (run to_html.py first)")
    if not pdf_path.exists():
        raise _errors.ToolError(f"error: PDF not found: {pdf_path} (run to_pdf.py first)")


def _open_reader(pdf_path: Path):
    try:
        return PdfReader(str(pdf_path))
    except Exception as exc:
        raise _errors.ToolError(f"error: cannot read {pdf_path}: {exc}") from exc


def _annotation_box(
    link: dict, page_number: int, page_width: float, page_height: float
) -> tuple[float, float, float, float]:
    """The link's rectangle in PDF points, clamped to the page box.

    Links near a printed page boundary can straddle the edge by a few points
    because browser CSS pixels and PDF points round differently; clamping keeps
    the annotation on the visible page.
    """
    rect = link["rect"]
    y_on_page = rect["y"] - page_number * VIEWPORT_HEIGHT
    x0 = rect["x"] * page_width / VIEWPORT_WIDTH
    x1 = (rect["x"] + rect["w"]) * page_width / VIEWPORT_WIDTH
    y0 = page_height - (y_on_page + rect["h"]) * page_height / VIEWPORT_HEIGHT
    y1 = page_height - y_on_page * page_height / VIEWPORT_HEIGHT
    x0 = max(0.0, min(x0, page_width))
    x1 = max(0.0, min(x1, page_width))
    y0 = max(0.0, min(y0, page_height))
    y1 = max(0.0, min(y1, page_height))
    if not (x0 < x1 and y0 < y1):
        raise RuntimeError(
            f"Invalid TOC link rectangle for {link['text'][:80]}: {(x0, y0, x1, y1)}"
        )
    return float(x0), float(y0), float(x1), float(y1)


def _drop_targetless_links(reader) -> int:
    """Remove link rectangles Chromium wrote without a destination.

    The split renderer stitches per-chapter PDFs, so a TOC entry that points into
    another part arrives as a clickable rectangle with neither /Dest nor /A. Left
    in place they pile up beside the annotations this step adds (975-page print
    edition: 647 dead + 644 real).
    """
    removed = 0
    for page in reader.pages:
        try:
            annots = page.get('/Annots')
        except Exception:
            continue
        if not annots:
            continue
        keep = []
        for ref in annots:
            obj = ref.get_object()
            # key presence, not truthiness: an empty /Dest array is still a target
            if obj.get('/Subtype') == '/Link' and '/Dest' not in obj \
                    and '/A' not in obj:
                removed += 1
                continue
            keep.append(ref)
        if len(keep) != len(annots):
            page[NameObject('/Annots')] = ArrayObject(keep)
    return removed


def _add_annotations(writer, reader, toc_links, outline_entries) -> int:
    """One link annotation per printed TOC entry; returns how many were added."""
    page_width = float(reader.pages[0].mediabox.width)
    page_height = float(reader.pages[0].mediabox.height)
    added = 0
    for link, (_, target_page) in zip(toc_links, outline_entries, strict=False):
        rect = link["rect"]
        center_y = rect["y"] + rect["h"] / 2
        page_number = int(center_y // VIEWPORT_HEIGHT)
        if page_number >= len(reader.pages):
            raise RuntimeError(
                f"TOC link outside PDF page range: {link['text'][:80]} -> page {page_number + 1}"
            )
        annotation = Link(
            rect=_annotation_box(link, page_number, page_width, page_height),
            target_page_index=int(target_page),
        )
        annotation[NameObject("/NM")] = TextStringObject(f"toc-link-{link['index']}")
        writer.add_annotation(page_number, annotation)
        added += 1
    return added


def add_links(
    pdf_path: Path | None = None,
    html_path: Path | None = None,
    tmp_path: Path | None = None,
    toc_links: list[dict] | None = None,
) -> None:
    # resolved when the step runs: the print edition passes its own pair
    html_path = Path(html_path) if html_path else Path(_config.merged_html())
    pdf_path = Path(pdf_path) if pdf_path else Path(_config.merged_pdf())
    tmp_path = Path(tmp_path) if tmp_path else pdf_path.with_suffix(".pdf.tmp")
    _require_inputs(html_path, pdf_path)

    if toc_links is None:
        toc_links = get_toc_links(html_path)
    print(f"TOC links in HTML: {len(toc_links)}")

    reader = _open_reader(pdf_path)
    outline_entries = collect_outline(reader)
    print(f"Outline entries in PDF: {len(outline_entries)}")

    if len(toc_links) > len(outline_entries):
        raise RuntimeError(
            f"TOC ({len(toc_links)}) exceeds outline entries ({len(outline_entries)})"
        )
    if toc_links and outline_entries:
        first_link = toc_links[0]["text"]
        first_outline = outline_entries[0][0]
        if first_link != first_outline:
            print(
                f'  Note: first TOC entry "{first_link[:40]}" != first outline "{first_outline[:40]}"'
            )

    print(f"TOC links to add: {len(toc_links)} / {len(outline_entries)} outline entries")
    dead = _drop_targetless_links(reader)
    if dead:
        print(f"  移除无目标的链接框: {dead}")

    writer = PdfWriter()
    # Use append() which preserves outlines (clone_document_from_reader may lose them)
    writer.append(reader)
    added = _add_annotations(writer, reader, toc_links, outline_entries)

    writer.write(str(tmp_path))
    # Validate the temporary file is readable before replacing the original.
    PdfReader(str(tmp_path))
    os.replace(tmp_path, pdf_path)
    print(f"TOC links added: {added}")
    # the last writer compresses: this rewrite inflated the file gs had already
    # shrunk, and compressing before it meant paying twice for one result
    from render import pdf_split  # noqa: PLC0415 - keeps the pdf renderer optional

    pdf_split.optimize(str(pdf_path))


if __name__ == "__main__":
    add_links()
