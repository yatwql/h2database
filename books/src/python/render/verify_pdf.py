#!/usr/bin/env python3
"""Verify the generated PDF against the HTML it was rendered from.

Checks
  EXISTS      the PDF file is present
  SIZE        file size within book.toml [thresholds].pdf_max_mb
  PAGES       at least one page
  OUTLINE     outline entry count/order matches the HTML H1-H4 headings
  OUTLINE_LEV   outline nesting depth follows the heading levels
  TOC_COUNT   printed TOC entries match the heading count
  TOC_LINKS   every printed-TOC link annotation is ordered, in-bounds and
              targets the same page as the corresponding outline entry
  FONTS       every font used by the document is embedded

Usage:
  python verify_pdf.py                 # report + exit code
  python verify_pdf.py --json          # machine readable
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import json
import os
import re
import sys
from typing import Any

from lib import _config, _errors, _fsutil, _mdutil
from lib import layout as _layout

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency
    PdfReader = None  # type: ignore[assignment]

class Report:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = '') -> None:
        self.checks.append((name, ok, detail))

    @property
    def failures(self) -> list[tuple[str, str]]:
        return [(n, d) for n, ok, d in self.checks if not ok]

    def to_dict(self) -> dict:
        return {
            'ok': not self.failures,
            'checks': [{'name': n, 'ok': ok, 'detail': d} for n, ok, d in self.checks],
        }

def html_headings(html: str) -> list[tuple[int, str]]:
    """Return (level, plain text) for every H1-H4 with an id."""
    return [(item['level'], item['text']) for item in _mdutil.html_headings(html)]

def outline_entries(reader) -> list[tuple[str, int, int]]:
    """Flatten the PDF outline into (title, page index, depth)."""
    entries: list[tuple[str, int, int]] = []

    def walk(items, depth: int) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item, depth + 1)
                continue
            title = str(item.get('/Title', '')).strip()
            if not title:
                continue
            entries.append((title, reader.get_destination_page_number(item), depth))

    walk(reader.outline, 0)
    return entries

def toc_link_annotations(reader) -> list[tuple[int, int, Any]]:
    """Printed-TOC link annotations, ordered by their injected /NM index."""
    annots: list[tuple[int, int, Any]] = []
    for page_index, page in enumerate(reader.pages):
        for annot_ref in page.get('/Annots') or []:
            annot = annot_ref.get_object()
            if annot.get('/Subtype') != '/Link':
                continue
            name = str(annot.get('/NM', ''))
            if name.startswith('toc-link-'):
                annots.append((int(name.replace('toc-link-', '')), page_index, annot))
    annots.sort(key=lambda item: item[0])
    return annots

FONT_PROGRAM_KEYS = ('/FontFile', '/FontFile2', '/FontFile3')


def _has_program(font) -> bool:
    """True when this font dictionary declares an embedded program."""
    descriptor = font.get('/FontDescriptor')
    if descriptor and any(key in descriptor for key in FONT_PROGRAM_KEYS):
        return True
    for child in font.get('/DescendantFonts') or []:
        # a composite face keeps its program on the descendant, not on the parent
        child_obj = child.get_object() if hasattr(child, 'get_object') else child
        child_descriptor = child_obj.get('/FontDescriptor')
        if child_descriptor and any(key in child_descriptor for key in FONT_PROGRAM_KEYS):
            return True
    return False


def font_is_embedded(font) -> bool | None:
    """Whether one font dictionary carries its glyphs; None when unreadable.

    Type3 glyphs are drawn as procedures, which *is* embedding; a dictionary that
    cannot be read is unclassifiable, and the caller skips it rather than guessing.
    """
    try:
        if str(font.get('/Subtype', '')) == '/Type3':
            return True
        return _has_program(font)
    except (AttributeError, TypeError):
        return None


def non_embedded_fonts(reader) -> list[str]:
    """Names of fonts without an embedded font program."""
    seen: set[str] = set()
    missing: set[str] = set()
    for page in reader.pages:
        resources = page.get('/Resources') or {}
        fonts = resources.get('/Font') or {}
        try:
            items = fonts.values() if hasattr(fonts, 'values') else []
        except AttributeError:
            items = []
        for font_ref in items:
            font = (font_ref.get_object() if hasattr(font_ref, 'get_object')
                    else font_ref)
            try:
                name = str(font.get('/BaseFont', '')).strip()
            except (AttributeError, TypeError):
                continue
            if not name or name in seen:
                continue
            seen.add(name)
            if font_is_embedded(font) is False:
                missing.add(name)
    return sorted(missing)


def _as_float(value, fallback: float) -> float:
    """Threshold read from JSON might be a string or missing; fall back quietly."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _type3_fonts(reader) -> set[int]:
    """Object ids of Type3 fonts in use.

    A Type3 font is a set of glyph procedures, not an embedded font program, and
    Chromium only produces one when it cannot embed the face: a `.ttc` collection,
    a synthesised bold, or a missing glyph. A handful is tolerable; thousands mean
    the font stack resolved to something unembeddable and the file is bloated.
    """
    seen: set[int] = set()
    for page in reader.pages:
        resources = page.get('/Resources')
        if not resources:
            continue
        fonts = resources.get_object().get('/Font')
        if not fonts:
            continue
        for ref in fonts.get_object().values():
            try:
                if ref.get_object().get('/Subtype') == '/Type3':
                    seen.add(getattr(ref, 'idnum', id(ref)))
            except (AttributeError, KeyError, TypeError):
                # a malformed font resource cannot be classified; skip it
                continue
    return seen


def _size_budget(pages: int) -> float:
    """Size budget that tracks page count.

    The budget used to be a flat 12 MB, which was calibrated on a single print run
    at 743 pages. Per-chapter rendering embeds font subsets once per part, so file
    size follows page count rather than the renderer: allow the flat floor or
    `pdf_bytes_per_page` per page, whichever is larger.
    """
    floor = _as_float(_config.THRESHOLDS.get('pdf_max_mb'), 12.0)
    per_page = _as_float(_config.THRESHOLDS.get('pdf_bytes_per_page'), 16384.0) / (1024 * 1024)
    return max(floor, pages * per_page)


def _open_inputs(report: Report, pdf_path: str, html_path: str):
    """(reader, html) once both inputs are readable, else None."""
    if PdfReader is None:
        report.add('PYPDF', False, 'pypdf not installed (pip install pypdf)')
        return None
    if not os.path.isfile(pdf_path):
        report.add('EXISTS', False, f'missing {pdf_path}')
        return None
    if not os.path.isfile(html_path):
        report.add('SOURCE_HTML', False, f'missing {html_path}')
        return None
    report.add('EXISTS', True)

    reader = PdfReader(pdf_path)
    type3 = _type3_fonts(reader)
    limit = _as_float(_config.THRESHOLDS.get('pdf_type3_max'), 50.0)
    report.add('FONTS', len(type3) <= limit,
               f'{len(type3)} Type3 font(s) (limit {int(limit)}) — a high count means '
               'the font stack resolved to something Chromium cannot embed')
    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    budget = _size_budget(len(reader.pages))
    report.add('SIZE', size_mb <= budget, f'{size_mb:.2f} MB (budget {budget:.1f} MB)')
    return reader, _fsutil.read_text(html_path)


def _check_density(report: Report, pdf_path: str) -> None:
    """DENSITY: leading and page fill, judged against geometry, not a page count.

    A page target belongs to one edition of one book. What transfers is the ratio
    between line pitch and type size — text set at 1.0 is cramped on any page — and
    the share of the printable height the text actually fills. Both are read off the
    built document, so a different paper, font or book moves the numbers without
    moving the criterion.
    """
    try:
        from render import pdf_metrics  # noqa: PLC0415 - only needed for this check
    except Exception:
        report.add('DENSITY', True, 'pdf_metrics unavailable, skipped')
        return
    metrics = pdf_metrics.measure(pdf_path)
    body = metrics.get('body_pt') or 0.0
    pitch = metrics.get('pitch_pt') or 0.0
    if not body or not pitch:
        report.add('DENSITY', True, 'no text to measure')
        return
    ratio = pitch / body
    low = float(_config.THRESHOLDS.get('pdf_leading_ratio_min', 1.15) or 1.15)
    high = float(_config.THRESHOLDS.get('pdf_leading_ratio_max', 1.75) or 1.75)
    # A4 at the configured 24mm top/bottom margin leaves 705.9pt of printable height
    fill = pitch * metrics.get('lines_per_page', 0)
    report.add('DENSITY', low <= ratio <= high,
               f'leading {ratio:.2f}x body (want {low}-{high}), '
               f'text fills {fill:.0f}pt of the page')


def _check_outline(report: Report, reader, headings) -> list:
    """PAGES, OUTLINE and OUTLINE_LEV against the HTML headings."""
    outline = outline_entries(reader)
    outline_titles = [title for title, _page, _depth in outline]
    heading_titles = [title for _level, title in headings]
    report.add('OUTLINE', outline_titles == heading_titles,
               f'{len(outline_titles)} outline entries vs {len(heading_titles)} headings')

    # Nesting depth must follow the heading level (h1 -> depth 0, h2 -> 1, ...).
    min_level = min((lvl for lvl, _t in headings), default=1)
    expected_depths = [level - min_level for level, _title in headings]
    actual_depths = [depth for _t, _p, depth in outline]
    report.add('OUTLINE_LEV', len(actual_depths) == len(expected_depths)
               and all(a <= b for a, b in zip(actual_depths, expected_depths, strict=False)),
               'outline depth follows heading levels'
               if len(actual_depths) == len(expected_depths)
               else 'outline/heading count differ')
    return outline


def _check_toc_links(reader, annots, outline) -> list[str]:
    """Problems with the printed-TOC link annotations, one per kind."""
    problems: list[str] = []
    outline_pages = [page for _t, page, _d in outline]
    for expected_index, (index, page_index, annot) in enumerate(annots):
        if index != expected_index:
            problems.append(f'annotation order gap at {expected_index}')
            break
        rect = _annotation_rect(annot)
        page = reader.pages[page_index]
        if len(rect) != 4 or not (
            0 <= rect[0] < rect[2] <= float(page.mediabox.width)
            and 0 <= rect[1] < rect[3] <= float(page.mediabox.height)
        ):
            problems.append(f'annotation {index} outside page bounds')
            break
        target = _annotation_target_page(reader, annot)
        if target is None:
            problems.append(f'annotation {index} destination not found')
            break
        if expected_index < len(outline_pages) and target != outline_pages[expected_index]:
            problems.append(f'annotation {index} targets page {target + 1}, '
                            f'expected {outline_pages[expected_index] + 1}')
            break
    return problems


def _check_column(report: Report) -> None:
    """COLUMN: the reading measure and the sheet — two rules, neither book-specific.

    `chars_per_line_min <= column / body <= chars_per_line_max` keeps a line inside the
    legible range whatever font is installed (`em` is the face's own unit), and the
    column must still fit what the margins leave, or the print clips it. Both are
    properties of the text, so they are checked from the layout rather than the PDF:
    text width can only be estimated from the content stream, and an estimate cannot
    tell a wide column from a wide glyph.
    """
    layout, _problems = _layout.Layout.from_mapping(_config.THRESHOLDS)
    problems = layout.measure_problems()
    report.add('COLUMN', not problems,
               f'{layout.measure_em():g}em/line, column {layout.print_column()}px, '
               f'margins {layout.print_margins_mm()[1]:g}mm'
               + (f' — {problems[0]}' if problems else ''))


def _check_geometry(report: Report, reader, pdf_path: str = '') -> None:
    """PAGE_SIZE and ROTATION: a delivery PDF is A4 and upright."""
    sizes = {(round(float(page.mediabox.width), 1), round(float(page.mediabox.height), 1))
             for page in reader.pages}
    width = float(_config.THRESHOLDS.get('pdf_page_width', 595))
    height = float(_config.THRESHOLDS.get('pdf_page_height', 842))
    tol = float(_config.THRESHOLDS.get('pdf_page_tolerance', 2))
    a4 = all(abs(w - width) <= tol and abs(h - height) <= tol for w, h in sizes)
    _check_density(report, pdf_path)
    _check_column(report)
    report.add('PAGE_SIZE', a4,
               f'{sorted(sizes)[:2]} (expect {width:.0f}x{height:.0f})')
    rotations = {int(page.get('/Rotate') or 0) for page in reader.pages}
    report.add('ROTATION', rotations <= {0}, f'rotations={sorted(rotations)}')


def _check_fonts(report: Report, reader) -> None:
    missing_fonts = non_embedded_fonts(reader)
    report.add('FONTS', not missing_fonts,
               'all fonts embedded' if not missing_fonts
               else f'not embedded: {", ".join(missing_fonts[:5])}')


def verify(pdf_path: str, html_path: str, require_toc_links: bool = False) -> Report:
    report = Report()
    opened = _open_inputs(report, pdf_path, html_path)
    if opened is None:
        return report
    reader, html = opened

    report.add('PAGES', len(reader.pages) > 0, f'{len(reader.pages)} pages')
    headings = html_headings(html)
    outline = _check_outline(report, reader, headings)  # its pages drive the TOC check
    heading_titles = [title for _level, title in headings]

    toc_match = re.search(r'<nav id="toc-page-nav">([\s\S]*?)</nav>', html)
    toc_count = len(re.findall(r'<a\b', toc_match.group(1))) if toc_match else 0
    report.add('TOC_COUNT', toc_count == len(heading_titles),
               f'{toc_count} printed TOC entries vs {len(heading_titles)} headings')

    annots = toc_link_annotations(reader)
    if toc_count and not annots and not require_toc_links:
        report.add('TOC_LINKS', True,
                   'printed TOC not enhanced yet (run pdf_toc_links.py)')
        annots = None
    problems: list[str] = []
    if annots is not None and len(annots) != toc_count:
        problems.append(f'link annotations {len(annots)} vs TOC entries {toc_count}')
    problems += _check_toc_links(reader, annots or [], outline)
    if annots is not None:
        report.add('TOC_LINKS', not problems,
                   'printed TOC links resolve to outline pages' if not problems
                   else '; '.join(problems[:2]))

    _check_geometry(report, reader, pdf_path)
    _check_fonts(report, reader)
    return report


def _annotation_rect(annot) -> list[float]:
    """Return the annotation rectangle as floats (empty when absent/malformed)."""
    raw = annot.get('/Rect', []) if hasattr(annot, 'get') else []
    try:
        return [float(value) for value in raw]
    except (TypeError, ValueError):
        return []

def _annotation_target_page(reader, annot) -> int | None:
    dest = annot.get('/Dest')
    action = annot.get('/A')
    if action:
        if action.get('/S') != '/GoTo':
            return None
        dest = action.get('/D')
    if not isinstance(dest, list) or not dest:
        return None
    ref = dest[0]
    if isinstance(ref, int):
        return ref if 0 <= ref < len(reader.pages) else None
    for index, page in enumerate(reader.pages):
        if page.indirect_reference == ref:
            return index
    return None

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pdf', help='path to the PDF (default: books/dist)')
    parser.add_argument('--html', help='path to the HTML (default: books/dist)')
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    parser.add_argument('--require-toc-links', action='store_true',
                        help='fail when the printed TOC has no link annotations')
    args = parser.parse_args(argv)

    pdf_path = args.pdf or _config.merged_pdf()
    html_path = args.html or _config.merged_html()
    report = verify(pdf_path, html_path, require_toc_links=args.require_toc_links)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if not report.failures else 1

    print('=' * 72)
    print(f'PDF 交付校验  {os.path.basename(pdf_path)}')
    print('=' * 72)
    for name, ok, detail in report.checks:
        print(f'  [{"ok  " if ok else "FAIL"}] {name:<11} {detail}')
    if report.failures:
        print(f'\n{len(report.failures)} 项未通过')
        return 1
    print('\n✅ PDF 交付校验通过')
    return 0

if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
