#!/usr/bin/env python3
"""Robust markdown to HTML converter - handles paired fences correctly."""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import re

import html_cache
from html_shell import STYLE
from lib import _config, _fsutil, _mdutil

_fsutil.pin_stdout_utf8()

docs_dir = _config.BOOK_ROOT
src_dir = _config.MANUSCRIPT_DIR
dist_dir = _config.DIST_DIR

INPUT = _config.merged_md()
OUTPUT = _config.merged_html()

_fsutil.ensure_dir(OUTPUT)

lines = _fsutil.read_lines(INPUT)

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


def md_to_html(text):
    # Inline link [label](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    return text

# Build TOC HTML (sidebar)
# The TOC header is the click target for collapsing the sidebar — making
# the whole row clickable instead of a tiny chevron at the corner is far
# easier to discover. Chevron rotates 180° when collapsed (handled in CSS
# via `body.sidebar-collapsed #sidebar-toggle .chev`).
toc_html = (
    '<button id="sidebar-toggle" type="button" '
    'aria-label="收起或展开目录侧栏" title="点击收起/展开目录（快捷键 [）">'
    '<span class="chev">‹</span><span class="lbl">TOC · 目录</span>'
    '</button>\n'
)
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

def render_body(body_lines):
    """Render body markdown to HTML; returns (html, fence count, unclosed-pre)."""
    content_parts: list[str] = []
    in_pre = False
    pre_lang = ''
    auto_exited = False
    fence_lines_found = 0
    for line in body_lines:
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
                content_parts.append('<pre><code>\n')
            else:
                in_pre = False
                pre_lang = ''
                content_parts.append('</code></pre>\n')
            continue

        if in_pre:
            hm = re.match(r'^(#{1,4})\s+(.+)$', stripped)
            if hm and pre_lang in ('', 'text'):
                in_pre = False
                auto_exited = True
                content_parts.append('</code></pre>\n')
            else:
                escaped = stripped.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                content_parts.append(escaped + '\n')
                continue

        m = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            anchor = _mdutil.slugify(title)
            content_parts.append(f'<h{level} id="{anchor}">{md_to_html(title)}</h{level}>\n')
            continue

        if stripped == '':
            content_parts.append('\n')
            continue
        if stripped == '---':
            content_parts.append('<hr>\n')
            continue

        # Figure caption: detect **图 X-Y: Title** pattern
        if stripped.startswith('**图 ') and stripped.endswith('**'):
            inner = stripped[2:-2]
            content_parts.append(f'<strong class="fig-caption">{md_to_html(inner)}</strong>\n')
        else:
            content_parts.append(f'<p>{md_to_html(stripped)}</p>\n')

    if in_pre:
        content_parts.append('</code></pre>\n')
    return ''.join(content_parts), fence_lines_found, in_pre


# Fragments are cached per H1 chapter: the TOC, the anchors and the numbering are
# already final here, so a fragment depends only on its own markdown and on the
# renderer's source. `--full` ignores the cache and re-renders every chapter.
FULL_REBUILD = '--full' in _sys.argv[1:]
renderer_fingerprint = html_cache.fingerprint(md_to_html, render_body)
content_parts: list[str] = []
fence_lines_found = 0
in_pre = False
reused = rendered = 0
chunk_keys: set[str] = set()
for chunk in html_cache.chunk_lines(lines[main_start:]):
    key = html_cache.key_for(chunk, renderer_fingerprint)
    chunk_keys.add(key)
    entry = None if FULL_REBUILD else html_cache.load(key)
    if entry is None:
        html, fences, unclosed = render_body(chunk)
        entry = {'html': html, 'fences': fences, 'unclosed': unclosed}
        html_cache.store(key, entry)
        rendered += 1
    else:
        reused += 1
    content_parts.append(entry['html'])
    fence_lines_found += int(entry.get('fences') or 0)
    in_pre = bool(entry.get('unclosed'))
html_cache.prune(chunk_keys)

content_html = ''.join(content_parts)

# Build cover HTML
cover_title = _config.project('display_title_en', _config.TITLE)
cover_subtitle = _config.project('display_title_zh', _config.TITLE)
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
# v5.6: capture author block lines (one or two `**Name:** value` lines under
# the version meta). They live above the description paragraph and must
# render visibly on the title page so HTML readers see authorship just like
# the printed cover. Both `cover.md` and `front/copyright.md` carry author
# lines (intentional — copyright stays formal, cover stays the public face)
# so deduplicate by stripping markdown emphasis + colon variants when
# comparing.
cover_author_lines: list[str] = []
seen_author_keys: set[str] = set()
for cl in cover_lines:
    cl = cl.strip()
    if cl.startswith('版本 '):
        cover_meta = cl
    elif cl.startswith('深入剖析'):
        cover_desc = cl
    elif cl.startswith('共 '):
        cover_tags = [t.strip() for t in cl.split('·')]
    elif cl.startswith(('**作者', '**联系邮箱')):
        # Build a normalised dedup key. Two on-disk forms exist:
        #   `**作者**: 其·龙` (colon outside bold, copyright style)
        #   `**作者：其·龙**` (colon inside bold, cover style)
        # Normalise both to "作者:其·龙" so they compare equal.
        key = re.sub(r'\*+', '', cl)
        key = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', key)  # [text](url) → text
        key = key.replace('：', ':')
        key = re.sub(r'\s*:\s*', ':', key)  # squeeze whitespace around colon
        key = re.sub(r'\s+', ' ', key).strip().lower()
        if key not in seen_author_keys:
            seen_author_keys.add(key)
            cover_author_lines.append(cl)

cover_author_html = ''
if cover_author_lines:
    cover_author_html = '<div class="author">\n'
    for line in cover_author_lines:
        cover_author_html += f'    <p>{md_to_html(line)}</p>\n'
    cover_author_html += '  </div>\n'

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
        if stripped.startswith('|') and stripped.endswith('|') and '---' not in stripped:
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
<title>{_config.project('display_title_en', _config.TITLE)}</title>
<style>{STYLE}</style>
</head>
<body>
<section id="cover">
  <h1>{cover_title}</h1>
  <h2>{cover_subtitle}</h2>
  <div class="divider"></div>
  <div class="meta">{md_to_html(cover_meta)}</div>
  {cover_author_html}
  <div class="desc">{md_to_html(cover_desc)}</div>
  {cover_info_table}
  {cover_tag_html}
  <div class="scroll-hint" onclick="document.getElementById('page-wrap').scrollIntoView({{behavior:'smooth'}})">▼ 向下浏览</div>
</section>
{toc_page_html}
<div style="position:absolute;left:0;top:0;width:1px;height:1px;overflow:hidden;" aria-hidden="true">__CONTENT_START__</div>
<div id="page-wrap" class="page-wrap">
  <button id="toggle-sidebar" onclick="document.getElementById('sidebar').classList.toggle('open')">TOC</button>
  <button id="sidebar-expand" type="button" aria-label="展开目录侧栏" title="展开目录侧栏（快捷键 [）">›</button>
  <nav id="sidebar">
  {toc_html}
  </nav>
  <main id="content">
  {content_html}
  </main>
</div>
<script>
// Desktop sidebar collapse/expand: clicking the TOC header bar at the
// top of the sidebar slides it off-screen to widen the reading area; a
// floating chevron at top-left brings it back. The choice persists in
// localStorage so the reader's preference survives page reloads.
//
// Implementation note: handlers are attached via document-level event
// delegation (using closest() to find the trigger). This is robust to
// late-injected DOM, IIFE ordering, and any framework that swaps button
// nodes — direct addEventListener bindings can silently fall off when
// the original button is replaced.
(function() {{
    const body = document.body;
    const KEY = 'h2-doc-sidebar-collapsed';
    if (localStorage.getItem(KEY) === '1') {{
        body.classList.add('sidebar-collapsed');
    }}
    function setCollapsed(collapsed) {{
        body.classList.toggle('sidebar-collapsed', collapsed);
        try {{ localStorage.setItem(KEY, collapsed ? '1' : '0'); }} catch (e) {{ /* private mode */ }}
    }}
    document.addEventListener('click', (e) => {{
        const t = e.target;
        if (!t || !t.closest) return;
        if (t.closest('#sidebar-toggle')) {{ e.preventDefault(); setCollapsed(true); return; }}
        if (t.closest('#sidebar-expand')) {{ e.preventDefault(); setCollapsed(false); return; }}
    }});
    // Keyboard shortcut: '[' toggles the sidebar (ignored when typing in form fields).
    document.addEventListener('keydown', (e) => {{
        if (e.key !== '[' || e.ctrlKey || e.metaKey || e.altKey) return;
        const tag = (e.target && e.target.tagName) || '';
        if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target.isContentEditable) return;
        setCollapsed(!body.classList.contains('sidebar-collapsed'));
    }});
}})();

// Intro mode: hide the sidebar while the reader is on cover/TOC pages so
// the fixed-left sidebar doesn't overlay centered cover content or the
// full-width TOC. Sidebar reappears once main content enters the viewport.
(function() {{
    const body = document.body;
    const pageWrap = document.getElementById('page-wrap');
    if (!pageWrap) return;
    body.classList.add('intro-mode');
    const introObserver = new IntersectionObserver((entries) => {{
        entries.forEach(entry => {{
            // Once #page-wrap (the main content container) enters the
            // viewport at all, leave intro mode and show the sidebar.
            if (entry.isIntersecting) {{
                body.classList.remove('intro-mode');
            }} else if (entry.boundingClientRect.top > 0) {{
                // #page-wrap has scrolled below the viewport again
                // (reader scrolled back up to cover/TOC) — re-hide sidebar.
                body.classList.add('intro-mode');
            }}
        }});
    }}, {{ rootMargin: '0px 0px -20% 0px' }});
    introObserver.observe(pageWrap);
}})();

// Scroll spy for sidebar
(function() {{
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
}})();

// Code block: line numbers + copy button
(function() {{
document.querySelectorAll('pre').forEach(pre => {{
    const code = pre.querySelector('code');
    if (!code || !code.textContent.trim()) return;
    const lines = code.innerHTML.split('\\n');
    const count = lines.length;

    // Create line numbers
    const lineNum = document.createElement('div');
    lineNum.className = 'line-nums';
    let nums = '';
    for (let i = 1; i <= count; i++) {{
        nums += i + '\\n';
    }}
    lineNum.textContent = nums;

    // Wrap code in code-content div
    const codeContent = document.createElement('div');
    codeContent.className = 'code-content';
    code.parentNode.insertBefore(codeContent, code);
    codeContent.appendChild(code);

    // Wrap everything in pre-wrap
    const wrap = document.createElement('div');
    wrap.className = 'pre-wrap';
    pre.insertBefore(wrap, pre.firstChild);
    wrap.appendChild(lineNum);
    wrap.appendChild(codeContent);

    // Copy button
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = '复制';
    btn.onclick = function() {{
        const text = code.textContent;
        if (navigator.clipboard) {{
            navigator.clipboard.writeText(text).then(() => {{
                btn.textContent = '已复制';
                setTimeout(() => {{ btn.textContent = '复制'; }}, 2000);
            }});
        }} else {{
            // Fallback for file:// protocol
            const ta = document.createElement('textarea');
            ta.value = text; ta.style.position = 'fixed'; ta.style.left = '-9999px';
            document.body.appendChild(ta); ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            btn.textContent = '已复制';
            setTimeout(() => {{ btn.textContent = '复制'; }}, 2000);
        }}
    }};
    wrap.appendChild(btn);
}});
}})();

// Breadcrumb navigation
(function() {{
const content = document.getElementById('content');
if (!content) return;
const headings = content.querySelectorAll('h1[id],h2[id],h3[id]');
if (headings.length === 0) return;

const breadcrumb = document.createElement('div');
breadcrumb.id = 'breadcrumb';

function updateBreadcrumb() {{
    let trail = [];
    headings.forEach(h => {{
        const rect = h.getBoundingClientRect();
        if (rect.top <= 120) {{
            const level = parseInt(h.tagName.substring(1));
            trail = trail.filter(t => t.level < level);
            trail.push({{ level: level, id: h.id, text: h.textContent.trim() }});
        }}
    }});
    let html = '<a href="#content">首页</a>';
    trail.forEach((item, i) => {{
        html += '<span class="sep">›</span>';
        if (i === trail.length - 1) {{
            html += `<span class="current">${{item.text.replace(/^第\\d+章/, '')}}</span>`;
        }} else {{
            html += `<a href="#${{item.id}}">${{item.text.replace(/^第\\d+章/, '')}}</a>`;
        }}
    }});
    breadcrumb.innerHTML = html;
}}

updateBreadcrumb();
window.addEventListener('scroll', updateBreadcrumb);
content.insertBefore(breadcrumb, content.firstChild);
}})();

// Chapter navigation (prev/next)
(function() {{
const chapters = [
  {{ id: '第1章-总体架构', title: '总体架构与分层模块划分' }},
  {{ id: '第2章-分层模块划分', title: '分层模块划分' }},
  {{ id: '第3章-核心包结构', title: '核心包结构' }},
  {{ id: '第4章-核心模块详解', title: '核心模块详解' }},
  {{ id: '第5章-核心流程解读', title: '核心流程解读' }},
  {{ id: '第6章-h2-数据库核心算法分析', title: '{_config.project("breadcrumb_root", "源码分析")}' }},
  {{ id: '第7章-sql-执行全流程', title: 'SQL 执行全流程' }},
  {{ id: '第8章-查询优化器', title: '查询优化器' }},
  {{ id: '第9章-持久化引擎深度解析', title: '持久化引擎深度解析' }},
  {{ id: '第10章-锁实现与并发控制', title: '锁实现与并发控制' }},
  {{ id: '第11章-核心源代码导读指引', title: '开发指南与调试' }},
  {{ id: '第12章-总结', title: '总结与对比' }},
];
const nav = document.createElement('div');
nav.id = 'chapter-nav';

function updateNav() {{
  let currentIdx = -1;
  chapters.forEach((ch, i) => {{
    const el = document.getElementById(ch.id);
    if (el) {{
      const rect = el.getBoundingClientRect();
      if (rect.top <= window.innerHeight / 2) currentIdx = i;
    }}
  }});
  let prevHtml = '', nextHtml = '';
  if (currentIdx > 0) {{
    prevHtml = `<a href="#${{chapters[currentIdx-1].id}}"><span class="nav-label">‹ 上一章</span><span class="nav-title">${{chapters[currentIdx-1].title}}</span></a>`;
  }} else {{
    prevHtml = `<span class="nav-disabled"><span class="nav-label">‹ 上一章</span></span>`;
  }}
  if (currentIdx >= 0 && currentIdx < chapters.length - 1) {{
    nextHtml = `<a href="#${{chapters[currentIdx+1].id}}"><span class="nav-label">下一章 ›</span><span class="nav-title">${{chapters[currentIdx+1].title}}</span></a>`;
  }} else {{
    nextHtml = `<span class="nav-disabled"><span class="nav-label">下一章 ›</span></span>`;
  }}
  nav.innerHTML = prevHtml + nextHtml;
}}

updateNav();
window.addEventListener('scroll', updateNav);
content.appendChild(nav);
}})();
</script>
</body>
</html>"""

_fsutil.write_text(OUTPUT, HTML)

print(f"Generated: {OUTPUT}")
print(f"TOC entries: {len(toc_entries)}")
print(f"Fence lines: {fence_lines_found}")
print(f"Unclosed pre at EOF: {in_pre}")
print(f"Chapter fragments: {reused} reused / {rendered} rendered")
