#!/usr/bin/env python3
"""
Generate the **EPUB** delivery for the H2 documentation.

EPUB sits alongside the standard PDF and the Phase G print-grade PDF as
an *on-demand* delivery format: it is produced only at the final
delivery stage, never as part of the daily MD/HTML pipeline.

Pandoc is the conversion engine. It already handles markdown -> EPUB 3
with proper TOC, ASCII-fence preservation, and chapter splitting; we
just hand it the merged ``h2-source-code-analysis.md`` plus a metadata
block and a small CSS sheet for typography.

Output: ``docs-stm/h2-source-code-analysis.epub``

Usage:
    python docs-stm/tools/generate_epub.py

Requires pandoc (https://pandoc.org/installing.html). Pandoc is *not*
required for any other step in the pipeline; this script is purely an
opt-in delivery tool.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import textwrap

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')

merged_md = os.path.join(docs_dir, 'h2-source-code-analysis.md')
epub_out = os.path.join(docs_dir, 'h2-source-code-analysis.epub')
cover_md = os.path.join(docs_dir, 'cover.md')


# ── Step 0: Pandoc availability check ────────────────────────────────────
pandoc = shutil.which('pandoc')
if not pandoc:
    print(
        "pandoc not found on PATH.\n"
        "Install it before running this script:\n"
        "  Windows :  winget install --id JohnMacFarlane.Pandoc -e\n"
        "             (or)  choco install pandoc\n"
        "  macOS   :  brew install pandoc\n"
        "  Debian  :  sudo apt install pandoc\n"
        "Then re-run:  python docs-stm/tools/generate_epub.py",
        file=sys.stderr,
    )
    sys.exit(1)
print(f"=== Step 0: pandoc detected at {pandoc} ===")
try:
    res = subprocess.run([pandoc, '--version'], capture_output=True, text=True, encoding='utf-8')
    first_line = (res.stdout or '').splitlines()[0] if res.stdout else ''
    if first_line:
        print(f"  {first_line}")
except Exception:
    pass


# ── Step 1: Ensure the merged Markdown is current ────────────────────────
print("\n=== Step 1: Ensuring merged Markdown is up to date ===")
rebuild = os.path.join(script_dir, 'rebuild_merged.py')
if os.path.exists(rebuild):
    res = subprocess.run(
        [sys.executable, rebuild],
        capture_output=True, text=True, encoding='utf-8',
        cwd=repo_root,
    )
    if res.returncode != 0:
        print("rebuild_merged.py FAILED:", res.stderr, file=sys.stderr)
        sys.exit(1)
    last = (res.stdout or '').strip().splitlines()[-1] if res.stdout else ''
    if last:
        print(f"  {last}")

if not os.path.exists(merged_md):
    print(f"Merged Markdown not found: {merged_md}", file=sys.stderr)
    sys.exit(1)


# ── Step 2: Extract title / version / author from cover.md ───────────────
title = "H2 Database Source Code Analysis"
subtitle = "H2 Database 源码全面分析与解读"
version = "v6.0"
author = "其·龙（Stallman Wang）"
publish_date = "2026-06-15"

if os.path.exists(cover_md):
    cover_text = open(cover_md, 'r', encoding='utf-8').read()
    m = re.search(r'^# (.+?)$', cover_text, re.MULTILINE)
    if m:
        title = m.group(1).strip()
    m = re.search(r'^## (.+?)$', cover_text, re.MULTILINE)
    if m:
        subtitle = m.group(1).strip()
    m = re.search(r'版本 (v[\d.]+) · (\d{4}-\d{2}-\d{2})', cover_text)
    if m:
        version = m.group(1)
        publish_date = m.group(2)
    m = re.search(r'\*\*作者：([^*]+?)\*\*', cover_text)
    if m:
        author = m.group(1).strip()


# ── Step 3: Build a metadata YAML block for pandoc ───────────────────────
# pandoc reads ``--metadata-file`` to populate EPUB ``<dc:title>``,
# ``<dc:creator>``, ``<dc:date>``, etc. We write the block to a temp file
# next to the merged Markdown so pandoc can pick up encoding correctly.
metadata_yaml = textwrap.dedent(f"""\
    ---
    title: "{title}"
    subtitle: "{subtitle}"
    author: "{author}"
    date: "{publish_date}"
    rights: "© {publish_date.split('-')[0]} {author}"
    lang: zh-CN
    publisher: "H2 Database 源码分析项目"
    description: "深入剖析 H2 Database v2.x 核心源码 — {version}"
    ---
    """)

metadata_path = os.path.join(docs_dir, '_epub_metadata.yaml')
with open(metadata_path, 'w', encoding='utf-8') as fh:
    fh.write(metadata_yaml)


# ── Step 4: Build a small CSS sheet for typography ───────────────────────
# Reading apps already render their own fonts, so we keep this minimal:
# tighter ASCII art, sensible heading rhythm, code-block contrast.
EPUB_CSS = """
/* H2 Database 源码分析 — EPUB stylesheet (minimal, reader-friendly) */
body { line-height: 1.55; font-family: "Source Han Serif", "Noto Serif CJK SC", serif; }
h1 { font-size: 1.6em; margin-top: 1.2em; page-break-before: always; color: #1565C0; }
h2 { font-size: 1.3em; margin-top: 1em; color: #1565C0; }
h3 { font-size: 1.1em; margin-top: 0.8em; color: #1976D2; }
h4 { font-size: 1em; margin-top: 0.6em; color: #455A64; }

pre, code {
    font-family: "Consolas", "DejaVu Sans Mono", "Source Han Mono SC", monospace;
}
pre {
    background: #f5f7fa;
    border-left: 3px solid #1565C0;
    padding: 0.6em 0.8em;
    overflow-x: auto;
    font-size: 0.85em;
    line-height: 1.35;
}
code { background: #f5f7fa; padding: 0 3px; border-radius: 2px; }

table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 0.9em;
}
th { background: #1565C0; color: #fff; padding: 6px 8px; text-align: left; }
td { border: 1px solid #ddd; padding: 6px 8px; }
tr:nth-child(even) td { background: #f9f9f9; }

blockquote {
    border-left: 3px solid #90caf9;
    margin: 1em 0;
    padding: 0.4em 0.8em;
    color: #455A64;
    background: #f5f9ff;
}

/* Figure caption pattern from the source: **图 X-Y: Title** rendered as <strong>. */
strong { font-weight: 600; }
"""

css_path = os.path.join(docs_dir, '_epub.css')
with open(css_path, 'w', encoding='utf-8') as fh:
    fh.write(EPUB_CSS)


# ── Step 5: Run pandoc ───────────────────────────────────────────────────
print(f"\n=== Step 2: Converting {merged_md} -> EPUB ===")

cmd = [
    pandoc,
    metadata_path,
    merged_md,
    '-o', epub_out,
    '--from=markdown+pipe_tables+fenced_code_blocks+backtick_code_blocks',
    '--to=epub3',
    '--toc',
    '--toc-depth=3',
    '--split-level=1',  # one H1 per chapter file inside the EPUB
    f'--css={css_path}',
    '--metadata=lang:zh-CN',
]

print(f"  Command: pandoc <metadata> <merged.md> -o <epub>")
print(f"           --toc --toc-depth=3 --split-level=1 --to=epub3")

try:
    res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if res.returncode != 0:
        print("pandoc FAILED:", file=sys.stderr)
        if res.stdout:
            print(res.stdout, file=sys.stderr)
        if res.stderr:
            print(res.stderr, file=sys.stderr)
        sys.exit(1)
    if res.stdout.strip():
        for line in res.stdout.splitlines():
            print(f"  {line}")
    if res.stderr.strip():
        # pandoc warnings go to stderr but are not fatal; surface them.
        for line in res.stderr.splitlines():
            print(f"  [pandoc warn] {line}")
except FileNotFoundError:
    print("pandoc executable disappeared between detection and invocation.",
          file=sys.stderr)
    sys.exit(1)
finally:
    # Tidy up the staging files; pandoc has already consumed them.
    for p in (metadata_path, css_path):
        try:
            os.remove(p)
        except OSError:
            pass


# ── Step 6: Report ───────────────────────────────────────────────────────
if not os.path.exists(epub_out):
    print(f"EPUB not produced at {epub_out}", file=sys.stderr)
    sys.exit(1)

size = os.path.getsize(epub_out)
print(f"\n=== Done ===")
print(f"EPUB:    {epub_out}")
print(f"Size:    {size:,} bytes ({size / 1024 / 1024:.2f} MB)")
print(f"Title:   {title}")
print(f"Version: {version}")
print(f"Author:  {author}")
print(f"Validate with epubcheck (optional):")
print(f"    java -jar epubcheck.jar {os.path.basename(epub_out)}")
