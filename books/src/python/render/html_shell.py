#!/usr/bin/env python3
"""HTML shell pieces for the single-file renderer: the stylesheet first.

The renderer is a flat script; its long literal blocks live here so the logic
stays readable. Moving text out must not change a byte of the output — the
build hash is the acceptance check.
"""
import os as _os
import sys as _sys

# importable from the renderer whether it runs as a script or as a module
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

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
    letter-spacing: 2px; margin-bottom: 1.5em; position: relative;
}
#cover .author {
    color: rgba(255,255,255,0.85); font-size: 0.95em;
    line-height: 1.8; margin-bottom: 2em; position: relative;
}
#cover .author p { margin: 0.2em 0; }
#cover .author a { color: #90caf9; text-decoration: none; border-bottom: 1px dotted rgba(144,202,249,0.5); }
#cover .author a:hover { color: #fff; border-bottom-color: #fff; }
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
    transition: opacity 0.25s ease, visibility 0.25s ease,
                transform 0.3s ease;
}
/* Hide the sidebar while reader is on cover or TOC page so it doesn't
   overlay the centered cover title and full-width table of contents.
   The sidebar reappears once the main content (#page-wrap) scrolls into
   view — handled by IntersectionObserver in the script below. */
body.intro-mode #sidebar { opacity: 0; visibility: hidden; pointer-events: none; }
body.intro-mode #toggle-sidebar { display: none; }
body.intro-mode #toc-page > div { margin-left: 0 !important; }
body.intro-mode #sidebar-expand { display: none; }

/* Desktop collapse: the TOC header row (#sidebar-toggle) acts as the
   collapse trigger. When collapsed, #sidebar slides off-screen to the
   left and #content drops its left margin to widen the reading area;
   the floating chevron #sidebar-expand at the top-left lets the reader
   bring the sidebar back. State persists in localStorage. */
#sidebar-expand {
    position: fixed; top: 12px; left: 12px; z-index: 150;
    width: 32px; height: 32px; padding: 0;
    background: #1a1a2e; color: #ccc;
    border: 1px solid rgba(255,255,255,0.15); border-radius: 4px;
    cursor: pointer; font-size: 16px; line-height: 30px;
    display: none; align-items: center; justify-content: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    transition: background 0.15s, color 0.15s;
}
#sidebar-expand:hover { background: #4fc3f7; color: #fff; border-color: #4fc3f7; }
body.sidebar-collapsed #sidebar { transform: translateX(-280px); }
body.sidebar-collapsed #content { margin-left: 0; max-width: 1100px; }
body.sidebar-collapsed #sidebar-expand { display: flex; }
#sidebar::-webkit-scrollbar { width: 5px; }
#sidebar::-webkit-scrollbar-thumb { background: #555; border-radius: 3px; }
/* TOC header row doubles as the collapse toggle — much clearer
   affordance than a tiny corner button. The chevron rotates 180° when
   the sidebar is collapsed (it's now reachable only via #sidebar-expand,
   but rotating in advance keeps the icon consistent across states). */
#sidebar-toggle {
    display: flex; align-items: center; gap: 8px;
    width: calc(100% - 24px); margin: 0 12px 8px; padding: 6px 12px 12px;
    background: transparent; border: none; border-bottom: 1px solid #333;
    color: #eee; font-size: 14px; letter-spacing: 1px; text-transform: uppercase;
    text-align: left; cursor: pointer; font-family: inherit;
    transition: color 0.15s, background 0.15s;
}
#sidebar-toggle:hover { color: #4fc3f7; background: rgba(79,195,247,0.05); }
#sidebar-toggle .chev {
    display: inline-block; font-size: 18px; line-height: 1;
    transition: transform 0.3s ease;
}
#sidebar-toggle .lbl { flex: 1; }
body.sidebar-collapsed #sidebar-toggle .chev { transform: rotate(180deg); }
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
    scroll-padding-left: 290px; scroll-padding-top: 20px;
    transition: margin-left 0.3s ease, max-width 0.3s ease;
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
    /* On mobile the hamburger toggle handles show/hide; suppress the
       desktop expand chevron to avoid two competing affordances. The
       sidebar header (#sidebar-toggle) stays visible since it's the
       TOC title; we just neutralise its collapse behaviour on mobile. */
    #sidebar-expand { display: none !important; }
    #sidebar-toggle { cursor: default; }
    #sidebar-toggle:hover { color: #eee; background: transparent; }
    #sidebar-toggle .chev { display: none; }
}
h1, h2, h3, h4 { color: #1565C0; margin-top: 1.5em; margin-bottom: 0.5em; font-family: 'Microsoft YaHei', SimSun, -apple-system, sans-serif; scroll-margin-left: 290px; scroll-margin-top: 20px; }
#content h1 { font-size: 1.8em; border-bottom: 2px solid #1565C0; padding-bottom: 8px; position: relative; padding-top: 0.3em; page-break-before: always; }
#content h1::before {
    content: ''; display: block; width: 60px; height: 4px;
    background: linear-gradient(90deg, #1565C0, #4fc3f7);
    border-radius: 3px; margin-bottom: 10px;
}
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
pre code { background: none; padding: 0; color: inherit; display: block; }

/* Code block: line numbers & copy button */
.pre-wrap { display: flex; position: relative; }
.line-nums {
    text-align: right; user-select: none; color: #999;
    border-right: 1px solid #ddd; margin-right: 8px;
    min-width: 28px; font-size: 11px; line-height: 1.0;
    background: #edeff2; padding: 12px 6px 12px 12px;
    flex-shrink: 0; border-radius: 3px 0 0 3px; overflow: hidden;
}
.code-content { flex: 1; overflow-x: auto; padding: 12px 0; }
.code-content code { padding: 0; }
.copy-btn {
    position: absolute; top: 4px; right: 4px; z-index: 10;
    background: rgba(255,255,255,0.85); border: 1px solid #d0d5dd;
    border-radius: 4px; padding: 2px 8px; font-size: 11px;
    cursor: pointer; color: #555; opacity: 0; transition: opacity 0.2s;
}
.pre-wrap:hover .copy-btn { opacity: 1; }
.copy-btn:hover { background: #e3f2fd; border-color: #1565C0; color: #1565C0; }

/* Breadcrumb navigation */
#breadcrumb {
    font-size: 13px; color: #888; margin-bottom: 1em; padding: 6px 0;
    border-bottom: 1px solid #eee; display: flex; flex-wrap: wrap; gap: 4px;
}
#breadcrumb .sep { color: #ccc; margin: 0 4px; }
#breadcrumb a { color: #1565C0; text-decoration: none; }
#breadcrumb a:hover { text-decoration: underline; }
#breadcrumb .current { color: #555; font-weight: 500; }

/* Chapter navigation */
#chapter-nav {
    margin-top: 3em; padding-top: 1.5em; border-top: 2px solid #e0e0e0;
    display: flex; justify-content: space-between; gap: 20px;
}
#chapter-nav a {
    display: inline-block; padding: 8px 16px; border: 1px solid #d0d5dd;
    border-radius: 6px; color: #1565C0; text-decoration: none;
    font-size: 14px; transition: all 0.2s; max-width: 45%;
}
#chapter-nav a:hover { background: #e3f2fd; border-color: #1565C0; }
#chapter-nav .nav-label { font-size: 11px; color: #999; display: block; }
#chapter-nav .nav-title { font-weight: 500; }

table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
th { background: #1565C0; color: white; font-weight: 600; position: sticky; top: 0; }
tr:nth-child(even) { background: #f9f9f9; }
tr:hover { background: #eef4fb; }

/* ===== Figure Captions ===== */
strong.fig-caption {
    display: block; margin: 0.5em 0 1em; padding: 6px 12px;
    background: #f0f6ff; border-left: 3px solid #1565C0;
    border-radius: 0 4px 4px 0; font-size: 0.92em; color: #1a3a5c;
    line-height: 1.6;
}

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
  #sidebar { display: none; }
  #content { margin-left: 0; max-width: 760px; width: auto; padding: 0; }
  pre, table { page-break-inside: avoid; }
  h1, h2, h3, h4 { page-break-after: avoid; }
  pre { font-size: 10px; }
  @page { size: A4; margin: 26mm 22mm; }
}
"""
