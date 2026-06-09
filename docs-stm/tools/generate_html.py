#!/usr/bin/env python3
"""Robust markdown to HTML converter - handles paired fences correctly."""
import os, re, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')

INPUT = os.path.join(docs_dir, 'h2-source-code-analysis.md')
OUTPUT = os.path.join(docs_dir, 'h2-source-code-analysis.html')

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

with open(INPUT, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find where main content starts (first # 第N章 heading)
main_start = 0
cover_text = ''
for i, line in enumerate(lines):
    if re.match(r'^# 第\d+章', line):
        main_start = i
        break
    cover_text += line

# Build TOC from main content only, tracking fence state
toc_entries = []
in_pre_toc = False
pre_toc_lang = ''
for i in range(main_start, len(lines)):
    raw_line = lines[i]
    stripped = raw_line.strip()
    if stripped.startswith('```'):
        if stripped.startswith('```mermaid'):
            continue
        lang = stripped[3:].strip()
        if not in_pre_toc:
            in_pre_toc = True
            pre_toc_lang = lang
        else:
            in_pre_toc = False
            pre_toc_lang = ''
        continue
    m = re.match(r'^(#{1,4})\s+(.+)$', raw_line.rstrip('\n'))
    if m:
        level = len(m.group(1))
        title = m.group(2).strip()
        anchor = title.lower()
        anchor = re.sub(r'[^\w一-鿿㐀-䶿\s-]', '', anchor)
        anchor = anchor.replace(' ', '-')
        # Never modify in_pre_toc when encountering a heading — doing so
        # corrupts fence state tracking for subsequent content. Only skip
        # if inside a non-text code block.
        if not (in_pre_toc and pre_toc_lang not in ('', 'text')):
            toc_entries.append((level, title, anchor, i))
        continue

STYLE = r"""
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { min-height: 100vh; }
body {
    font-family: -apple-system, 'Microsoft YaHei', sans-serif;
    line-height: 1.8; color: #333; background: #fafafa;
    display: flex; flex-direction: column;
}
html { overflow-y: scroll; }

/* ===== Cover Info Table ===== */
.cover-info { background: rgba(79,195,247,0.08); border: 1px solid rgba(79,195,247,0.2); border-radius: 8px; margin: 1.5em auto; width: auto; min-width: 280px; max-width: 520px; }
.cover-info th { background: transparent; color: #90caf9; font-weight: 600; text-align: center; border: none; padding: 6px 8px; font-size: 0.82em; letter-spacing: 1px; }
.cover-info td { color: rgba(255,255,255,0.75); border: none; padding: 5px 12px; font-size: 0.88em; }
.cover-info tr:nth-child(even) { background: rgba(255,255,255,0.03); }
.cover-info tr:hover { background: rgba(79,195,247,0.1); }

/* ===== Cover Page ===== */
#cover {
    min-height: 100vh; display: flex; flex-direction: column;
    justify-content: center; align-items: center; text-align: center;
    background-color: #0d1b2a;
    background: linear-gradient(135deg, #0d1b2a 0%, #1b2838 40%, #1a3a5c 100%);
    color: #fff; padding: 40px 20px; position: relative; overflow: hidden;
    isolation: isolate; flex-shrink: 0;
}
#cover::before {
    content: ''; position: absolute; top: -50%; left: -50%;
    width: 200%; height: 200%; z-index: -1;
    background: radial-gradient(ellipse at 30% 40%, rgba(79,195,247,0.08) 0%, transparent 60%),
                radial-gradient(ellipse at 70% 60%, rgba(255,152,0,0.05) 0%, transparent 50%);
    pointer-events: none;
}
#cover h1 {
    color: #fff; font-size: 2.6em; font-weight: 700; border: none;
    letter-spacing: 2px; margin: 0 0 0.3em; text-shadow: 0 2px 20px rgba(0,0,0,0.3);
    position: relative; z-index: 1; flex-shrink: 0;
}
#cover h2 {
    color: #90caf9; font-size: 1.3em; font-weight: 400; border: none;
    letter-spacing: 4px; margin: 0 0 2em; position: relative; z-index: 1; flex-shrink: 0;
}
#cover .divider {
    width: 80px; height: 3px; background: linear-gradient(90deg, #4fc3f7, #1565C0);
    margin: 0 auto 2em; border-radius: 2px; position: relative;
}
#cover .meta {
    color: rgba(255,255,255,0.6); font-size: 0.95em;
    letter-spacing: 2px; margin-bottom: 2.5em; position: relative;
}
#cover .desc {
    max-width: 600px; color: rgba(255,255,255,0.75);
    font-size: 1em; line-height: 2; margin-bottom: 1.5em; position: relative;
}
#cover .tags {
    display: flex; flex-wrap: wrap; gap: 10px; justify-content: center;
    margin-bottom: 3em; position: relative;
}
#cover .tags span {
    background: rgba(79,195,247,0.15); border: 1px solid rgba(79,195,247,0.25);
    padding: 4px 14px; border-radius: 20px; font-size: 0.82em; color: #90caf9;
}
#cover .scroll-hint {
    position: absolute; bottom: 30px; color: rgba(255,255,255,0.3);
    font-size: 0.8em; letter-spacing: 2px; cursor: pointer;
    animation: bounce 2s infinite;
}
@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(8px); }
}

/* ===== Layout ===== */
.page-wrap { display: flex; flex: 1; }

#sidebar {
    position: fixed; left: 0; top: 0; bottom: 0; width: 280px;
    background: #1a1a2e; color: #ccc; overflow-y: auto;
    padding: 20px 0; z-index: 100;
}
#sidebar::-webkit-scrollbar { width: 5px; }
#sidebar::-webkit-scrollbar-thumb { background: #555; border-radius: 3px; }
#sidebar h2 {
    color: #eee; font-size: 14px; padding: 0 16px 12px;
    border-bottom: 1px solid #333; margin: 0 12px 8px;
    letter-spacing: 1px; text-transform: uppercase;
}
#sidebar a {
    display: block; color: #aaa; text-decoration: none;
    padding: 4px 16px 4px 12px; font-size: 13px;
    border-left: 3px solid transparent; transition: all 0.15s;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
#sidebar a:hover, #sidebar a.active {
    color: #fff; background: rgba(255,255,255,0.05);
    border-left-color: #4fc3f7;
}
#sidebar .toc-h2 { padding-left: 24px; font-size: 12.5px; }
#sidebar .toc-h3 { padding-left: 38px; font-size: 12px; color: #888; }
#sidebar .toc-h4 { padding-left: 52px; font-size: 11.5px; color: #777; }
#content {
    margin-left: 280px; flex: 1; max-width: 960px;
    padding: 40px 48px; background: #fff; min-height: 100vh;
}
#toggle-sidebar {
    display: none; position: fixed; top: 12px; left: 12px; z-index: 200;
    background: #1a1a2e; color: #fff; border: none; border-radius: 4px;
    padding: 8px 12px; cursor: pointer; font-size: 18px;
}
@media (max-width: 768px) {
    #sidebar { left: -280px; transition: left 0.3s; }
    #sidebar.open { left: 0; }
    #content { margin-left: 0; padding: 48px 20px 20px; }
    #toggle-sidebar { display: block; }
}
h1, h2, h3, h4 { color: #1565C0; margin-top: 1.5em; margin-bottom: 0.5em; font-family: 'Microsoft YaHei', SimSun, -apple-system, sans-serif; }
h1 { font-size: 1.8em; border-bottom: 2px solid #1565C0; padding-bottom: 8px; }
h2 { font-size: 1.4em; border-bottom: 1px solid #e0e0e0; padding-bottom: 5px; }
h3 { font-size: 1.15em; }
h4 { font-size: 1.05em; color: #333; }
p { margin: 0.8em 0; text-align: justify; }
code {
    background: #f0f4f8; padding: 2px 6px; border-radius: 3px;
    font-family: Consolas, 'Courier New', monospace; font-size: 0.9em;
    color: #2d3748;
}
pre {
    background: #f4f5f7; padding: 12px; border-radius: 6px;
    overflow-x: auto; font-size: 12px; line-height: 1.0;
    font-family: Consolas, 'DengXian', SimSun, monospace;
    border: 1px solid #d0d5dd; border-left: 4px solid #1565C0;
    margin: 1em 0; color: #1a1a2e;
}
pre code { background: none; padding: 0; color: inherit; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
th { background: #1565C0; color: white; font-weight: 600; }
tr:nth-child(even) { background: #f9f9f9; }
blockquote {
    border-left: 4px solid #1565C0; margin: 1em 0;
    padding: 0.5em 1em; background: #f5f5f5; color: #555;
}
a { color: #1565C0; text-decoration: none; }
a:hover { text-decoration: underline; }
hr { border: none; border-top: 1px solid #ddd; margin: 2em 0; }
ul, ol { margin: 0.5em 0; padding-left: 2em; }
li { margin: 0.3em 0; }

/* ===== TOC Page ===== */
#toc-page { background: #fff; padding: 20px 0; }
#toc-page a:hover { background: #f0f4f8 !important; text-decoration: none; }
@media (min-width: 769px) {
  #toc-page > div { margin-left: 280px !important; }
}
@media print {
  #toc-page { page-break-after: always; }
  #cover { page-break-after: always; }
}
"""

def md_to_html(text):
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    return text

# Build TOC HTML (sidebar)
toc_html = '<h2>TOC</h2>\n'
for level, title, anchor, _ in toc_entries:
    indent = f'toc-h{level}'
    toc_html += f'<a class="{indent}" href="#{anchor}">{md_to_html(title)}</a>\n'

# Build TOC page entries (h1-h4 full structure, matching sidebar TOC)
toc_page_entries = [e for e in toc_entries if e[0] <= 4]

# Build TOC page HTML (full-width, placed between cover and content)
toc_page_html = '<section id="toc-page">\n'
toc_page_html += '  <div style="max-width:720px;margin:0 auto;padding:40px 20px;">\n'
toc_page_html += '    <h1 style="text-align:center;border:none;color:#1565C0;margin-bottom:30px;">目录</h1>\n'
toc_page_html += '    <hr style="width:60px;margin:0 auto 30px;border-color:#1565C0;">\n'
toc_page_html += '    <nav id="toc-page-nav">\n'
for level, title, anchor, _ in toc_page_entries:
    indent_px = 0 if level == 1 else (level - 1) * 20
    font_size = 16 if level == 1 else (15 if level == 2 else (14 if level == 3 else 13))
    font_weight = 'bold' if level <= 2 else 'normal'
    color = '#1565C0' if level == 1 else ('#333' if level == 2 else ('#555' if level == 3 else '#777'))
    margin_b = '10px' if level <= 2 else '6px'
    toc_page_html += (
        f'      <div style="margin-left:{indent_px}px;margin-bottom:{margin_b};'
        f'font-size:{font_size}px;font-weight:{font_weight};color:{color};">\n'
    )
    toc_page_html += f'        <a href="#{anchor}" style="color:inherit;text-decoration:none;display:block;padding:2px 8px;border-radius:3px;">{md_to_html(title)}</a>\n'
    toc_page_html += '      </div>\n'
toc_page_html += '    </nav>\n'
toc_page_html += '  </div>\n'
toc_page_html += '</section>\n'

# Build content HTML from main content only (skip cover)
content_html = ''
in_pre = False
pre_lang = ''
auto_exited = False
fence_lines_found = 0
for line in lines[main_start:]:
    stripped = line.rstrip('\n')
    is_fence = stripped.startswith('```')

    if is_fence:
        fence_lines_found += 1
        lang = stripped[3:].strip()
        if not in_pre:
            if auto_exited and not lang:
                # Bare ``` after auto-exit: consume it (closes original fence)
                auto_exited = False
                continue
            auto_exited = False  # ```text/```java starts fresh
            in_pre = True
            pre_lang = lang
            content_html += '<pre><code>\n'
        else:
            in_pre = False
            pre_lang = ''
            content_html += '</code></pre>\n'
        continue

    if in_pre:
        hm = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if hm and pre_lang in ('', 'text'):
            in_pre = False
            auto_exited = True
            content_html += '</code></pre>\n'
        else:
            escaped = stripped.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            content_html += escaped + '\n'
            continue

    m = re.match(r'^(#{1,4})\s+(.+)$', stripped)
    if m:
        level = len(m.group(1))
        title = m.group(2).strip()
        anchor = title.lower()
        anchor = re.sub(r'[^\w一-鿿㐀-䶿\s-]', '', anchor)
        anchor = anchor.replace(' ', '-')
        content_html += f'<h{level} id="{anchor}">{md_to_html(title)}</h{level}>\n'
        continue

    if stripped == '':
        content_html += '\n'
        continue
    if stripped == '---':
        content_html += '<hr>\n'
        continue

    content_html += f'<p>{md_to_html(stripped)}</p>\n'

if in_pre:
    content_html += '</code></pre>\n'

# Build cover HTML
cover_title = 'H2 Database Source Code Analysis'
cover_subtitle = 'H2 Database 源码全面分析与解读'
cover_lines = cover_text.strip().split('\n')
for cl in cover_lines:
    cl = cl.strip()
    if cl.startswith('# ') and not cl.startswith('# 第'):
        cover_title = cl[2:].strip()
    elif cl.startswith('## ') and '源代码' not in cl:
        cover_subtitle = cl[3:].strip()

# Extract meta content (the paragraph lines in the cover)
cover_desc = ''
cover_meta = ''
cover_tags = []
for cl in cover_lines:
    cl = cl.strip()
    if cl.startswith('版本 '):
        cover_meta = cl
    elif cl.startswith('深入剖析'):
        cover_desc = cl
    elif cl.startswith('共 '):
        cover_tags = [t.strip() for t in cl.split('·')]

cover_tag_html = ''
if cover_tags:
    cover_tag_html = '<div class="tags">\n'
    for t in cover_tags:
        cover_tag_html += f'    <span>{md_to_html(t)}</span>\n'
    cover_tag_html += '  </div>\n'

# Extract 源代码信息 table from cover
cover_info_table = ''
in_info_section = False
for raw_line in cover_text.strip().split('\n'):
    stripped = raw_line.strip()
    if stripped == '## 源代码信息':
        in_info_section = True
        continue
    if in_info_section:
        if stripped.startswith('#') or stripped == '---':
            break
        if stripped.startswith('|') and stripped.endswith('|'):
            if '---' not in stripped:
                cells = [c.strip() for c in stripped.split('|')[1:-1]]
                if cells:
                    if not cover_info_table:
                        cover_info_table = '<table class="cover-info">\n<thead><tr>'
                        for c in cells:
                            cover_info_table += f'<th>{md_to_html(c)}</th>'
                        cover_info_table += '</tr></thead>\n<tbody>\n'
                    else:
                        cover_info_table += '<tr>'
                        for c in cells:
                            cover_info_table += f'<td>{md_to_html(c)}</td>'
                        cover_info_table += '</tr>\n'
if cover_info_table:
    cover_info_table += '</tbody>\n</table>\n'

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>H2 Database Source Code Analysis</title>
<style>{STYLE}</style>
</head>
<body>
<section id="cover">
  <h1>{cover_title}</h1>
  <h2>{cover_subtitle}</h2>
  <div class="divider"></div>
  <div class="meta">{md_to_html(cover_meta)}</div>
  <div class="desc">{md_to_html(cover_desc)}</div>
  {cover_info_table}
  {cover_tag_html}
  <div class="scroll-hint" onclick="document.getElementById('page-wrap').scrollIntoView({{behavior:'smooth'}})">▼ 向下浏览</div>
</section>
{toc_page_html}
<div style="position:absolute;left:0;top:0;width:1px;height:1px;overflow:hidden;" aria-hidden="true">__CONTENT_START__</div>
<div id="page-wrap" class="page-wrap">
  <button id="toggle-sidebar" onclick="document.getElementById('sidebar').classList.toggle('open')">TOC</button>
  <nav id="sidebar">
  {toc_html}
  </nav>
  <main id="content">
  {content_html}
  </main>
</div>
<script>
const observer = new IntersectionObserver((entries) => {{
    entries.forEach(entry => {{
        if (entry.isIntersecting) {{
            document.querySelectorAll('#sidebar a').forEach(a => a.classList.remove('active'));
            const id = entry.target.id;
            const link = document.querySelector(`#sidebar a[href="#${{id}}"]`);
            if (link) link.classList.add('active');
        }}
    }});
}}, {{ rootMargin: '-20% 0px -70% 0px' }});
document.querySelectorAll('h1[id],h2[id],h3[id],h4[id]').forEach(h => observer.observe(h));
</script>
</body>
</html>"""

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(HTML)

print(f"Generated: {OUTPUT}")
print(f"TOC entries: {len(toc_entries)}")
print(f"Fence lines: {fence_lines_found}")
print(f"Unclosed pre at EOF: {in_pre}")
