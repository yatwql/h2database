#!/usr/bin/env python3
"""Verify generated PDF outline and printed-TOC clickability."""
from __future__ import annotations

from pathlib import Path
import re

from pypdf import PdfReader

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DOCS_DIR = REPO_ROOT / 'docs-stm'
PDF = DOCS_DIR / 'h2-source-code-analysis.pdf'
HTML = DOCS_DIR / 'h2-source-code-analysis.html'

reader = PdfReader(str(PDF))
html = HTML.read_text(encoding='utf-8')

html_headings = re.findall(r'<h([1-4])\s+id="[^"]*"[^>]*>(.*?)</h\1>', html, re.S)
html_heading_titles = [re.sub(r'<[^>]+>', '', raw).strip() for _, raw in html_headings]
# Printed TOC page shows h1-h2 only (structural overview)
toc_heading_titles = [t for (lv, _), t in zip(html_headings, html_heading_titles) if int(lv) <= 2]

toc_match = re.search(r'<nav id="toc-page-nav">([\s\S]*?)</nav>', html)
toc_count = len(re.findall(r'<a\b', toc_match.group(1))) if toc_match else 0

outline_entries: list[tuple[str, int]] = []

def collect(items) -> None:
    for item in items:
        if isinstance(item, list):
            collect(item)
            continue
        title = str(item.get('/Title', '')).strip()
        if not title:
            continue
        outline_entries.append((title, reader.get_destination_page_number(item)))

collect(reader.outline)
outline_titles = [title for title, _ in outline_entries]
outline_pages = [page for _, page in outline_entries]

# Gather TOC annotations that we added (identified by /NM prefix).
toc_link_annots = []
for page_index, page in enumerate(reader.pages):
    annots = page.get('/Annots') or []
    for annot_ref in annots:
        annot = annot_ref.get_object()
        if annot.get('/Subtype') != '/Link':
            continue
        name = str(annot.get('/NM', ''))
        if name.startswith('toc-link-'):
            index = int(name.replace('toc-link-', ''))
            toc_link_annots.append((index, page_index, annot))

toc_link_annots.sort(key=lambda item: item[0])

failures: list[str] = []
if len(outline_titles) != len(html_heading_titles):
    failures.append(f'outline/html heading mismatch: {len(outline_titles)} vs {len(html_heading_titles)}')
if toc_count != len(toc_heading_titles):
    failures.append(f'HTML printed TOC/html heading (h1-h2) mismatch: {toc_count} vs {len(toc_heading_titles)}')
if outline_titles != html_heading_titles:
    first = next((i for i, (a, b) in enumerate(zip(outline_titles, html_heading_titles)) if a != b), None)
    failures.append(f'outline/html title order mismatch at index {first}: {outline_titles[first] if first is not None else "n/a"} != {html_heading_titles[first] if first is not None else "n/a"}')
if len(toc_link_annots) != toc_count:
    failures.append(f'PDF printed TOC link count mismatch: {len(toc_link_annots)} vs {toc_count}')
if any(p < 0 or p >= len(reader.pages) for p in outline_pages):
    failures.append('PDF outline contains invalid page targets')

for expected_index, (index, page_index, annot) in enumerate(toc_link_annots):
    if index != expected_index:
        failures.append(f'TOC annotation order gap: expected {expected_index}, got {index}')
        break
    rect = [float(v) for v in annot.get('/Rect', [])]
    if len(rect) != 4:
        failures.append(f'TOC annotation {index} has invalid rect')
        break
    page = reader.pages[page_index]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    x0, y0, x1, y1 = rect
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        failures.append(f'TOC annotation {index} rectangle outside page bounds: {rect}')
        break
    action = annot.get('/A')
    dest = annot.get('/Dest')
    if action:
        if action.get('/S') != '/GoTo':
            failures.append(f'TOC annotation {index} has non-GoTo action')
            break
        dest = action.get('/D')
    if not isinstance(dest, list) or len(dest) < 1:
        failures.append(f'TOC annotation {index} missing destination')
        break
    target_ref = dest[0]
    target_page = None
    if isinstance(target_ref, int):
        target_page = target_ref
    else:
        for pi, candidate in enumerate(reader.pages):
            if candidate.indirect_reference == target_ref:
                target_page = pi
                break
    if target_page is None or target_page < 0 or target_page >= len(reader.pages):
        failures.append(f'TOC annotation {index} destination page not found')
        break
    expected_target = outline_pages[index]
    if target_page != expected_target:
        failures.append(f'TOC annotation {index} targets page {target_page + 1}, expected {expected_target + 1}')
        break

print(f'PDF pages: {len(reader.pages)}')
print(f'HTML headings: {len(html_heading_titles)}')
print(f'Outline entries: {len(outline_titles)}')
print(f'HTML printed TOC entries: {toc_count}')
print(f'PDF printed TOC link annotations: {len(toc_link_annots)}')
print(f'PDF size: {PDF.stat().st_size:,} bytes')

if failures:
    print('FAILURES:')
    for failure in failures:
        print(' -', failure)
    raise SystemExit(1)
print('PDF verification passed')
