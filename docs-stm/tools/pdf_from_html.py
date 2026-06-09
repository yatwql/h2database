#!/usr/bin/env python3
"""Generate PDF from existing HTML (no HTML rebuild)."""
import io, sys, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')
html_path = os.path.join(docs_dir, 'h2-source-code-analysis.html')
pdf_path = os.path.join(docs_dir, 'h2-source-code-analysis.pdf')
os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

headings = []
for m in re.finditer(r'<h([1-4])\s+id="([^"]*)"[^>]*>(.*?)</h\1>', html_content, re.DOTALL):
    level = int(m.group(1))
    anchor_id = m.group(2)
    raw_html = m.group(3)
    plain = re.sub(r'<[^>]+>', '', raw_html).strip()
    plain = plain.replace('​', '')
    headings.append((level, plain, anchor_id))

print(f'Parsed {len(headings)} headings from HTML')

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
    page = browser.new_page()
    file_url = 'file:///' + html_path.replace('\\', '/')
    page.goto(file_url, wait_until='networkidle', timeout=60000)
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

    headings_json = page.evaluate("""() => {
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
            result.push({index: i, id: h.id, text: h.textContent.trim(), level: parseInt(h.tagName.substring(1))});
        });
        return result;
    }""")
    print(f'Injected {len(headings_json)} heading markers')

    page.pdf(path=pdf_path, format='A4',
             margin={'top': '20mm', 'bottom': '25mm', 'left': '15mm', 'right': '15mm'},
             print_background=True, display_header_footer=False, prefer_css_page_size=False)
    browser.close()
print('PDF rendered')

reader = PdfReader(pdf_path)
writer = PdfWriter()
for p in reader.pages:
    writer.add_page(p)

page_texts = []
for p in reader.pages:
    raw = p.extract_text() or ''
    page_texts.append(re.sub(r'\s+', '', raw))

marker_ok = any('__hdr_0__' in pt for pt in page_texts)
print(f'Markers in PDF: {marker_ok}')

if marker_ok:
    search_keys = [(h['level'], h['text'], '__hdr_{}__'.format(h['index'])) for h in headings_json]
else:
    print('Markers not found, falling back to text matching')
    search_keys = [(level, plain, re.sub(r'\s+', '', plain)) for level, plain, _ in headings]

content_start = 0
if marker_ok:
    for i, pt in enumerate(page_texts):
        if '__content__' in pt:
            content_start = i
            break
else:
    sample_keys = [sk[2] for sk in search_keys[:30]]
    match_counts = []
    for pt in page_texts:
        count = sum(1 for sk in sample_keys if sk in pt)
        match_counts.append(count)
    for i, count in enumerate(match_counts):
        if i > 0 and match_counts[i-1] >= 10 and count < 10:
            content_start = i
            break
    if content_start == 0:
        content_start = min(2, len(page_texts))
    print(f'Content start: page {content_start}')

outline_stack = {}
found_count = 0
not_found = []
current_page = content_start

for level, text, search_key in search_keys:
    page_num = None
    for i in range(current_page, len(page_texts)):
        if len(search_key) >= 3 and search_key in page_texts[i]:
            page_num = i
            break
    if page_num is None and len(search_key) >= 5:
        short_key = search_key[:20]
        for i in range(current_page, len(page_texts)):
            if short_key in page_texts[i]:
                page_num = i
                break
    if page_num is not None:
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

print(f'Outlines: {found_count} / {len(search_keys)}')
if not_found:
    print(f'Not found ({len(not_found)}):')
    for t in not_found[:5]:
        print(f'  - {t[:60]}')

writer.write(pdf_path)
print('PDF saved')
