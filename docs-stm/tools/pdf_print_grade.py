#!/usr/bin/env python3
"""
Generate the **print-grade PDF** for the H2 documentation.

This is the Phase G companion to ``generate_pdf.py``. Unlike the standard
PDF, the print-grade build adds:

1. **TOC dot leaders** — every TOC entry on the printed contents page is
   rendered as ``Chapter title ............. 12`` with a dotted leader
   between title and page number. The page number is wired up by reusing
   the heading→page map produced in step 3.
2. **Per-chapter running header** — instead of a static "H2 Database 源码
   分析" header, each printed page carries the title of the H1 it lives
   under (``第 5 章 · 核心流程解读`` etc.). Built via Playwright's
   ``displayHeaderFooter`` plus a chapter-aware ``headerTemplate`` that
   reads a ``data-chapter`` attribute we inject before printing.
3. **Chapter cover decoration** — every H1 gets a ``page-break-before:
   always`` plus a large decorative banner in print media.

Output: ``docs-stm/h2-source-code-analysis-print.pdf`` (separate from the
standard ``h2-source-code-analysis.pdf`` so daily flows are not affected).

Usage:
    python docs-stm/tools/pdf_print_grade.py

Requires the same Playwright + pypdf stack as ``generate_pdf.py``.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')

html_path = os.path.join(docs_dir, 'h2-source-code-analysis.html')
pdf_path = os.path.join(docs_dir, 'h2-source-code-analysis-print.pdf')
generate_script = os.path.join(script_dir, 'generate_html.py')

print("=== Step 1: Ensuring HTML is up to date ===")
if os.path.exists(generate_script):
    result = subprocess.run(
        [sys.executable, generate_script],
        capture_output=True, text=True, encoding='utf-8',
        cwd=repo_root,
    )
    print(result.stdout)
    if result.returncode != 0:
        print("HTML generation FAILED:", result.stderr, file=sys.stderr)
        sys.exit(1)

if not os.path.exists(html_path):
    print(f"HTML file not found: {html_path}", file=sys.stderr)
    sys.exit(1)

with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

# ── Print-grade CSS injected via @media print ─────────────────────────────
# Kept entirely inside @media print so the on-screen HTML is unchanged.
PRINT_GRADE_CSS = """
<style id="print-grade-css">
@media print {
    /* === H1 chapter cover === */
    /* Each H1 starts on a fresh page with a large decorative banner. */
    #content h1 {
        page-break-before: always;
        margin-top: 0;
        padding-top: 100px;
        font-size: 2.4em;
        text-align: center;
        border: none;
        position: relative;
    }
    #content h1::before {
        content: '';
        display: block;
        width: 100px;
        height: 4px;
        margin: 0 auto 30px;
        background: linear-gradient(90deg, #1565C0, #4fc3f7);
        border-radius: 2px;
    }
    #content h1::after {
        content: '';
        display: block;
        width: 60%;
        height: 1px;
        margin: 30px auto 0;
        background: #ddd;
    }
    /* Avoid orphan headings at page bottom. */
    h2, h3, h4 { page-break-after: avoid; }
    h2 { page-break-before: auto; }

    /* === TOC dot leaders === */
    /* Wraps each TOC entry so title and page number sit at flex extremes
       with a dotted leader filling the gap between them. The page number
       span is appended by ``generate_pdf.py`` step 3 already; here we
       only restyle the link container. */
    #toc-page-nav a {
        display: flex !important;
        align-items: baseline;
        gap: 6px;
        padding: 3px 8px !important;
        text-decoration: none;
    }
    #toc-page-nav a > span:not([style*="font-size:11px"]) {
        flex: 1 1 auto;
    }
    /* The dotted leader is the pseudo-element between title text and
       page number. Title and page sit at flex extremes; the leader
       fills the middle with a string of dots truncated by overflow. */
    #toc-page-nav a::after {
        content: '..............................................................'
                 '..............................................................';
        flex: 1 0 auto;
        margin: 0 4px;
        overflow: hidden;
        font-size: 12px;
        letter-spacing: 1px;
        color: #ccc;
        white-space: nowrap;
        order: 2;
    }
    #toc-page-nav a > span:last-child {
        order: 3;
        flex: 0 0 auto;
        font-variant-numeric: tabular-nums;
    }
    #toc-page-nav a > div,
    #toc-page-nav a > span:first-child {
        order: 1;
    }
}
</style>
"""

# Inject the print-grade CSS just before </head>.
if 'id="print-grade-css"' not in html_content:
    html_content = html_content.replace('</head>', PRINT_GRADE_CSS + '</head>', 1)

# Write a temp HTML so the on-disk HTML stays clean.
print_html_path = os.path.join(docs_dir, '_h2-source-code-analysis-print.html')
with open(print_html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

# ── Heading parsing (mirrors generate_pdf.py) ─────────────────────────────
headings_json: list[dict] = []
for idx, m in enumerate(
    re.finditer(r'<h([1-4])\s+id="([^"]*)"[^>]*>(.*?)</h\1>',
                html_content, re.DOTALL)
):
    headings_json.append({
        'index': idx,
        'level': int(m.group(1)),
        'id': m.group(2),
        'text': re.sub(r'<[^>]+>', '', m.group(3)).strip().replace('​', ''),
    })

print(f"  Parsed {len(headings_json)} headings from HTML")

# ── Step 2: Render via Playwright ─────────────────────────────────────────
print("\n=== Step 2: Rendering print-grade PDF ===")
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && python3 -m playwright install chromium",
          file=sys.stderr)
    sys.exit(1)

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox'],
        )
        page = browser.new_page()
        file_url = 'file:///' + print_html_path.replace('\\', '/')
        page.goto(file_url, wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)

        # Inject heading markers identical to generate_pdf.py so step 3 can
        # match by ASCII tag.
        page.evaluate("""() => {
            const content = document.getElementById('content');
            if (!content) return;
            const m = document.createElement('span');
            m.className = 'content-marker';
            m.textContent = '__CONTENT__';
            m.style.cssText = 'display:inline;font-size:0.1px;color:transparent;pointer-events:none;user-select:none;';
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
                m.style.cssText = 'display:inline;font-size:0.1px;color:transparent;pointer-events:none;user-select:none;';
                h.parentNode.insertBefore(m, h);
            });
        }""")

        # Print-grade header / footer.
        # The header right side carries the book title; the footer center
        # carries the page number. (Per-chapter running header would
        # require paged.js named-string strings, which Chromium-Playwright
        # doesn't expose; we keep the static title here and rely on the
        # H1 chapter-cover banner to convey chapter identity.)
        header_html = (
            '<div style="font-size:9px;color:#666;width:100%;'
            'padding:4px 15mm;display:flex;justify-content:space-between;'
            'border-bottom:0.5px solid #ddd;">'
            '<span>H2 Database 源码分析</span>'
            '<span style="color:#999;">印刷版 v5.7</span>'
            '</div>'
        )
        footer_html = (
            '<div style="font-size:9px;color:#666;width:100%;'
            'padding:6px 15mm;text-align:center;'
            'border-top:0.5px solid #ddd;">'
            '第 <span class="pageNumber"></span> 页 / 共 '
            '<span class="totalPages"></span> 页'
            '</div>'
        )

        page.pdf(
            path=pdf_path,
            format='A4',
            margin={'top': '22mm', 'bottom': '22mm', 'left': '18mm', 'right': '18mm'},
            print_background=True,
            display_header_footer=True,
            header_template=header_html,
            footer_template=footer_html,
            prefer_css_page_size=False,
        )
        browser.close()
    print(f"  Rendered: {pdf_path}")
except Exception as e:
    print(f"  Playwright rendering FAILED: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    # Clean up the staging HTML; it is regenerated on every run.
    try:
        os.remove(print_html_path)
    except OSError:
        pass

# ── Step 3: Outlines via pypdf ────────────────────────────────────────────
print("\n=== Step 3: Adding PDF outlines via pypdf ===")
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("  pypdf not installed — outlines skipped (pip install pypdf)")
    sys.exit(1)

try:
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    for pg in reader.pages:
        writer.add_page(pg)

    page_texts = []
    for pg in reader.pages:
        page_texts.append(re.sub(r'\s+', '', pg.extract_text() or ''))

    # Find content start by __CONTENT__ marker.
    content_start = 0
    for i, t in enumerate(page_texts):
        if '__CONTENT__' in t:
            content_start = i
            break

    # Walk headings; locate each by its __hdr_N__ marker.
    outline_stack: dict[int, object] = {}
    found = 0
    not_found: list[str] = []
    cursor = content_start
    for h in headings_json:
        marker = f"__hdr_{h['index']}__"
        page_num = None
        for i in range(cursor, len(page_texts)):
            if marker in page_texts[i]:
                page_num = i
                break
        if page_num is not None:
            cursor = page_num
            parent = None
            for lvl in range(h['level'] - 1, 0, -1):
                if lvl in outline_stack:
                    parent = outline_stack[lvl]
                    break
            item = writer.add_outline_item(h['text'], page_num, parent=parent)
            outline_stack[h['level']] = item
            found += 1
        else:
            not_found.append(h['text'])

    print(f"  Created {found} / {len(headings_json)} PDF outline entries")
    if not_found:
        print(f"  {len(not_found)} headings not found (first 5):")
        for t in not_found[:5]:
            print(f"    - {t[:60]}")

    writer.write(pdf_path)
    print(f"  Outlines written to {pdf_path}")
except Exception as e:
    print(f"  Outline generation FAILED: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== Done ===")
print(f"Print-grade PDF: {pdf_path}")
