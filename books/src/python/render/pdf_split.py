#!/usr/bin/env python3
"""Render the PDF one H1 chapter at a time, then merge.

Why this exists: printing the whole document in one `page.pdf()` call is subject
to a whole-page fit-to-scale step that normalises density — page margins, column
width and font size all landed inside 725–754 pages whatever the value, and a
*larger* body font produced *fewer* pages (impossible without a hidden scale).
Rendering each chapter into its own page box keeps every chapter at 1:1, so the
typography decides pagination again, and the outline is computed from chapter
page offsets instead of searching layout-dependent markers (see rf-44).
"""
from __future__ import annotations

import contextlib
import os
import re
import tempfile
from typing import Any

MARKER_RE = re.compile(r'__hdr_(\d+)__')

SPLIT_JS = '''() => {
    const content = document.getElementById('content');
    if (!content) return [];
    const html = content.innerHTML;
    // split at H1 boundaries; the first chunk may be empty
    const chunks = html.split(/(?=<h1\\b)/i).map(s => s.trim()).filter(Boolean);
    return chunks.map(chunk => {
        const holder = document.createElement('div');
        holder.innerHTML = chunk;
        const heads = [...holder.querySelectorAll('h1, h2, h3, h4')].map(h => ({
            level: parseInt(h.tagName.substring(1)),
            text: h.textContent.trim(),
        }));
        return {html: chunk, headings: heads};
    });
}'''


def _strip_ws(text: str) -> str:
    return re.sub(r'\s+', '', text)


def _page_texts(pdf_path: str) -> list[str]:
    from pypdf import PdfReader
    return [_strip_ws(page.extract_text() or '') for page in PdfReader(pdf_path).pages]


def render_parts(page, work_dir: str, pdf_kwargs: dict, headings: list[dict]) -> tuple[list[str], list[dict]]:
    """Render front matter and every chapter; returns (pdf paths, outline entries).

    Headings are located by the `__hdr_<index>__` markers the caller injects into
    each heading (3px white text, so they survive as real text in the layer). The
    index is global, so the marker maps straight back to `headings` — no title
    search, which used to lose entries to line wrapping and repeated short titles.
    """
    # lay the content out at the paper width (A4 at 96dpi) before printing, or
    # Chromium paginates against the 800x600 default viewport and doubles the count
    page.set_viewport_size({'width': 794, 'height': 1123})
    parts = page.evaluate(SPLIT_JS)
    if not parts:
        raise RuntimeError('no chapters found in #content')

    by_index = {h['index']: h for h in headings if 'index' in h}
    seen: set[int] = set()
    paths: list[str] = []
    entries: list[dict] = []
    offset = 0

    front = os.path.join(work_dir, 'part-000.pdf')
    page.evaluate("() => { const c = document.getElementById('content'); if (c) c.style.display = 'none'; }")
    page.pdf(path=front, **pdf_kwargs)
    offset += len(_page_texts(front))
    paths.append(front)

    # the cover and the printed TOC belong to the front part only
    page.evaluate('''() => {
        for (const id of ['cover', 'toc-page']) {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        }
    }''')
    for index, part in enumerate(parts, start=1):
        target = os.path.join(work_dir, f'part-{index:03d}.pdf')
        page.evaluate(
            '(payload) => { const c = document.getElementById("content");'
            ' c.style.display = "block"; c.innerHTML = payload.html; }', part)
        page.pdf(path=target, **pdf_kwargs)
        texts = _page_texts(target)
        paths.append(target)

        for local, text in enumerate(texts):
            for raw in MARKER_RE.findall(text):
                head = by_index.get(int(raw))
                if head is not None and head['index'] not in seen:
                    seen.add(head['index'])
                    entries.append({'level': head['level'], 'text': head['text'],
                                    'page': offset + local})
        offset += len(texts)
    return paths, entries


def merge(paths: list[str], pdf_path: str, entries: list[dict]) -> int:
    """Concatenate the parts and write the outline; returns the page count."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for part in paths:
        for page_obj in PdfReader(part).pages:
            writer.add_page(page_obj)

    stack: dict[int, Any] = {}
    for entry in entries:
        parent: Any = None
        for level in sorted(stack):
            if level < entry['level']:
                parent = stack[level]
        stack[entry['level']] = writer.add_outline_item(
            title=entry['text'], page_number=entry['page'], parent=parent)
        for level in [lvl for lvl in stack if lvl > entry['level']]:
            del stack[level]
    # each part carries its own font subsets and background resources; merging
    # them leaves duplicates, so collapse identical objects before writing
    # (without this the merged file is ~3x the single-print size).
    with contextlib.suppress(Exception):
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    writer.write(pdf_path)
    return len(writer.pages)


def render(page, pdf_path: str, pdf_kwargs: dict, headings: list[dict]) -> int:
    """Split-render into a temporary directory, merge, and report the page count."""
    work = tempfile.mkdtemp(prefix='pdf-split-')
    try:
        paths, entries = render_parts(page, work, pdf_kwargs, headings)
        count = merge(paths, pdf_path, entries)
        print(f'  Rendered {len(paths) - 1} chapter part(s) + front matter: {count} pages')
        print(f'  Outline entries: {len(entries)}')
        return count
    finally:
        for name in sorted(os.listdir(work)):
            with contextlib.suppress(OSError):
                os.remove(os.path.join(work, name))
        with contextlib.suppress(OSError):
            os.rmdir(work)
