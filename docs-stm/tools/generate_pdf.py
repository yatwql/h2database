#!/usr/bin/env python3
"""
Generate PDF from the H2 documentation HTML using Playwright/Chromium.

This script:
1) Regenerates the HTML from markdown
2) Converts HTML to PDF via Playwright (Chromium)
3) Post-processes the PDF with pypdf to add clickable outlines/bookmarks
   for the table-of-contents sidebar in PDF readers

Outline detection uses heading match DENSITY to automatically skip
the printed TOC page(s), then searches for each heading's exact page.
This avoids false matches caused by the TOC listing ALL heading texts.

Requirements:
    pip install playwright pypdf
    python3 -m playwright install chromium

Usage:
    python docs-stm/tools/generate_pdf.py

Output: docs-stm/h2-source-code-analysis.pdf
"""
import os, sys, io, subprocess, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')

# Step 1: Ensure HTML is up to date
html_path = os.path.join(docs_dir, 'h2-source-code-analysis.html')
pdf_path = os.path.join(docs_dir, 'h2-source-code-analysis.pdf')
os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
generate_script = os.path.join(script_dir, 'generate_html.py')

print("=== Step 1: Generating HTML ===")
if os.path.exists(generate_script):
    result = subprocess.run(
        [sys.executable, generate_script],
        capture_output=True, text=True, encoding='utf-8',
        cwd=repo_root
    )
    print(result.stdout)
    if result.returncode != 0:
        print("HTML generation FAILED:", result.stderr, file=sys.stderr)
        sys.exit(1)
else:
    print(f"Using existing HTML at {html_path}")

if not os.path.exists(html_path):
    print(f"HTML file not found: {html_path}", file=sys.stderr)
    sys.exit(1)

html_size = os.path.getsize(html_path)
print(f"\n=== Step 2: Converting HTML to PDF ===")
print(f"Input:  {html_path} ({html_size:,} bytes)")
print(f"Output: {pdf_path}")

# ── Parse headings from HTML first (used in both Step 2 and Step 3) ────────
with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

headings = []  # (level, plain_text, anchor_id)
for m in re.finditer(
    r'<h([1-4])\s+id="([^"]*)"[^>]*>(.*?)</h\1>',
    html_content, re.DOTALL
):
    level = int(m.group(1))
    anchor_id = m.group(2)
    raw_html = m.group(3)
    # Strip any inner HTML tags to get plain text
    plain = re.sub(r'<[^>]+>', '', raw_html).strip()
    plain = plain.replace('​', '')  # zero-width spaces
    headings.append((level, plain, anchor_id))

print(f"  Parsed {len(headings)} headings from HTML")

# ══════════════════════════════════════════════════════════════════════════
# Step 2: Convert HTML to PDF via Playwright
# ══════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
    sys.exit(1)

print("Launching Chromium via Playwright...")
headings_json = []
generated_with_markers = False
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = browser.new_page()

        # Load the HTML file
        file_url = 'file:///' + html_path.replace('\\', '/')
        page.goto(file_url, wait_until='networkidle', timeout=60000)

        # Wait for fonts and rendering to settle
        page.wait_for_timeout(3000)

        # Wait for Mermaid diagrams to render
        try:
            page.wait_for_selector('.mermaid svg', timeout=15000)
            print("  Mermaid diagrams rendered successfully")
        except Exception as e:
            print(f"  Mermaid rendering note: {e}")

        # ── Inject invisible ASCII markers for PDF outline detection ───────────
        # Each heading gets a unique marker like __HDR_0__, __HDR_1__, ...
        # These are searchable in the PDF text layer (ASCII text is extracted
        # reliably by pypdf, unlike CJK text which can be garbled).
        # font-size:0.1px + color:transparent keeps them invisible while still
        # rendering into the PDF text layer.

        # Content marker: placed at the very start of #content
        page.evaluate('''() => {
            const content = document.getElementById('content');
            if (!content) return;
            const marker = document.createElement('span');
            marker.className = 'content-marker';
            marker.textContent = '__CONTENT__';
            marker.style.cssText = 'display:inline;font-size:0.1px;color:transparent;pointer-events:none;user-select:none;';
            content.insertBefore(marker, content.firstChild);
        }''')

        # Heading markers: one before each heading
        headings_json = page.evaluate('''() => {
            const content = document.getElementById('content');
            if (!content) return [];
            const els = content.querySelectorAll('h1[id], h2[id], h3[id], h4[id]');
            const result = [];
            els.forEach((h, i) => {
                const marker = document.createElement('span');
                marker.className = 'hdr-marker';
                marker.textContent = '__hdr_' + i + '__';
                marker.style.cssText = 'display:inline;font-size:0.1px;color:transparent;pointer-events:none;user-select:none;';
                h.parentNode.insertBefore(marker, h);
                result.push({
                    index: i,
                    id: h.id,
                    text: h.textContent.trim(),
                    level: parseInt(h.tagName.substring(1)),
                });
            });
            return result;
        }''')

        print(f"  Injected {len(headings_json)} heading markers")

        # Print to PDF
        page.pdf(
            path=pdf_path,
            format='A4',
            margin={
                'top': '20mm',
                'bottom': '25mm',
                'left': '15mm',
                'right': '15mm',
            },
            print_background=True,
            display_header_footer=False,
            prefer_css_page_size=False,
        )

        browser.close()
    generated_with_markers = True
    print("  PDF rendered via Playwright successfully")
except Exception as e:
    print(f"  Playwright rendering FAILED: {e}", file=sys.stderr)
    print("  Refusing to reuse an existing PDF because it may be stale.", file=sys.stderr)
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════
# Step 3: Post-process with pypdf to add PDF outlines (bookmarks)
# ══════════════════════════════════════════════════════════════════════════
# Strategy: First try to find the reliable ASCII markers (__HDR_N__).
# If markers aren't found in the PDF text layer, fall back to heading text
# matching with smart TOC-page detection.
print(f"\n=== Step 3: Adding PDF outlines via pypdf ===")
try:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    # Copy all pages into the writer
    for p in reader.pages:
        writer.add_page(p)

    def strip_ws(t: str) -> str:
        """Remove ALL whitespace for fuzzy comparison."""
        return re.sub(r'\s+', '', t)

    # Pre-extract page text (once) for speed
    page_texts = []
    for p in reader.pages:
        raw = p.extract_text() or ''
        page_texts.append(strip_ws(raw))

    # ── Try Strategy A: Find markers in PDF ────────────────────────────────
    marker_mode = False
    # Inject the marker data into page_texts as unique search keys
    search_keys = []
    for h in headings_json:
        marker_text = f'__hdr_{h["index"]}__'
        search_keys.append((h['level'], h['text'], marker_text))
        marker_mode = True

    # Check if any marker was found in the PDF
    any_marker_found = False
    if marker_mode:
        test_marker = f'__hdr_0__'
        for pt in page_texts:
            if test_marker in pt:
                any_marker_found = True
                break

    # ── Strategy B: Fall back to heading text matching ─────────────────────
    if not marker_mode or not any_marker_found:
        if marker_mode:
            print("  Markers not found in PDF text layer — falling back to heading text matching")
        marker_mode = False

        # Build normalized heading texts
        search_keys = []
        for level, plain, anchor_id in headings:
            search_keys.append((level, plain, strip_ws(plain)))

    # ── Detect content start ────────────────────────────────────────────────
    # Use heading match density to find the transition from TOC page(s)
    # to actual content pages. TOC pages match MANY headings; content
    # pages match only 1-5.
    content_start = 0

    if not marker_mode:
        # Use a sample of 30 headings to measure per-page match density
        sample_keys = [sk[2] for sk in search_keys[:30]]
        match_counts = []
        for pt in page_texts:
            count = sum(1 for sk in sample_keys if sk in pt)
            match_counts.append(count)

        # Find the first page where density drops from high (>10) to low (<10)
        # This marks the transition from TOC page to content page.
        prev_count = match_counts[0] if match_counts else 0
        for i, count in enumerate(match_counts):
            if i > 0 and prev_count >= 10 and count < 10:
                content_start = i
                break
            prev_count = count

        # Fallback: default to page 2 if detection failed
        if content_start == 0:
            content_start = min(2, len(page_texts))

        print(f"  Content start detected at page {content_start} "
              f"(density: page {content_start-1} had {match_counts[content_start-1]}/30, "
              f"page {content_start} has {match_counts[content_start]}/30)")
    else:
        # With markers, look for the content marker
        for i, pt in enumerate(page_texts):
            if '__content__' in pt:
                content_start = i
                break
        if content_start == 0:
            # Fallback: find first heading marker
            for i, pt in enumerate(page_texts):
                if '__hdr_0__' in pt:
                    content_start = i
                    break
        if content_start == 0:
            content_start = min(2, len(page_texts))
        print(f"  Content start detected at page {content_start} (marker mode)")

    # ── Build outlines with monotonic page search ───────────────────────────
    # Key insight: search for each heading STARTING from the page where the
    # PREVIOUS heading was found. This avoids false matches from cross-references
    # and summaries that appear on earlier pages. Headings in the PDF are in
    # document order (non-decreasing page numbers), so this constraint is valid.
    outline_stack: dict[int, object] = {}
    found_count = 0
    not_found = []
    current_page = content_start

    for level, text, search_key in search_keys:
        page_num = None

        # Primary search: from current_page (monotonic)
        if len(search_key) >= 3:
            for i in range(current_page, len(page_texts)):
                if search_key in page_texts[i]:
                    page_num = i
                    break

        # Fallback: shorter match
        if page_num is None:
            for i in range(current_page, len(page_texts)):
                short_key = search_key[:20]
                if len(short_key) >= 5 and short_key in page_texts[i]:
                    page_num = i
                    break

        if page_num is not None:
            # Advance current_page but NOT past page_num, so subsequent
            # headings on the same page still find it.
            current_page = page_num
            parent = None
            for l in range(level - 1, 0, -1):
                if l in outline_stack:
                    parent = outline_stack[l]
                    break
            item = writer.add_outline_item(text, page_num, parent=parent)
            outline_stack[level] = item
            found_count += 1
        else:
            not_found.append(text)

    print(f"  Created {found_count} / {len(search_keys)} PDF outline entries")
    if not_found:
        print(f"  {len(not_found)} headings not found in PDF (first 10):")
        for t in not_found[:10]:
            print(f"    - {t[:60]}")
        raise RuntimeError(f"Incomplete PDF outline: {found_count}/{len(search_keys)} headings resolved")

    # ── Build heading-to-page mapping for TOC page number injection ──────
    heading_pages_found = []
    current_page = content_start
    for level, text, search_key in search_keys:
        pn = None
        if len(search_key) >= 3:
            for i in range(current_page, len(page_texts)):
                if search_key in page_texts[i]:
                    pn = i
                    break
        if pn is None:
            for i in range(current_page, len(page_texts)):
                short_key = search_key[:20]
                if len(short_key) >= 5 and short_key in page_texts[i]:
                    pn = i
                    break
        if pn is not None:
            current_page = pn
        heading_pages_found.append(pn)

    # ── Inject page numbers into the HTML TOC page ───────────────────────
    # This adds [page N] labels after each TOC entry so they show up in
    # future PDF renders (when Chromium is available).
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        nav_marker = '<nav id="toc-page-nav">'
        nav_start = html.find(nav_marker)
        if nav_start > 0:
            nav_end = html.find('</nav>', nav_start)
            toc_section = html[nav_start:nav_end]

            def inject_page_no(m):
                full = m.group(0)
                # full = <a href="..." style="...">INNER_HTML</a>
                inner = m.group(2)
                # Strip HTML tags from inner to get plain text
                inner_plain = re.sub(r'<[^>]+>', '', inner).strip()
                inner_norm = strip_ws(inner_plain)
                for (lvl, txt, sk), pn in zip(search_keys, heading_pages_found):
                    if pn is not None and strip_ws(txt) == inner_norm:
                        page_num_span = f'<span style="font-size:11px;color:#999;font-weight:normal;"> [{pn+1}]</span>'
                        # Insert the page number span before the closing </a>
                        new_full = full.rstrip('</a>')
                        new_full += page_num_span + '</a>'
                        return new_full
                return full

            updated = re.sub(r'<a([^>]*)>(.*?)</a>', inject_page_no, toc_section)
            html = html[:nav_start] + updated + html[nav_end:]
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print("  Page numbers added to HTML TOC")
    except Exception as e:
        print(f"  TOC page number injection: {e}")

    # Overwrite the PDF with the outline-enhanced version
    writer.write(pdf_path)
    print("  Outlines written OK")

except ImportError:
    print("  pypdf not installed — outlines skipped (pip install pypdf)")
    sys.exit(1)
except Exception as e:
    print(f"  Outline generation FAILED: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)

file_size = os.path.getsize(pdf_path)
print(f"\n=== PDF Generated Successfully ===")
print(f"Path: {pdf_path}")
print(f"Size: {file_size:,} bytes ({file_size/1024:.1f} KB)")