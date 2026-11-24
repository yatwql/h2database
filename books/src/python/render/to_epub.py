#!/usr/bin/env python3
"""
Generate the **EPUB** delivery for the H2 documentation.

EPUB sits alongside the standard PDF and the print-grade PDF as
an *on-demand* delivery format: it is produced only at the final
delivery stage, never as part of the daily MD/HTML pipeline.

Pandoc is the conversion engine. It already handles markdown -> EPUB 3
with proper TOC, ASCII-fence preservation, and chapter splitting; we
just hand it the merged Markdown plus a metadata
block and a small CSS sheet for typography.

Output: ``books/<merged_name>.epub``

Usage:
    python books/tools/to_epub.py

Requires pandoc (https://pandoc.org/installing.html). Pandoc is *not*
required for any other step in the pipeline; this script is purely an
opt-in delivery tool.
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import contextlib
import datetime
import os
import re
import shutil
import subprocess
import sys
import textwrap

from lib import _config, _errors, _fsutil, fonts
from lib import layout as _layout

_fsutil.pin_stdout_utf8()

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..', '..'))
docs_dir = os.path.join(repo_root, 'books')
src_dir = _config.MANUSCRIPT_DIR
dist_dir = os.path.join(docs_dir, 'dist')

merged_md = _config.merged_md()
epub_out = _config.merged_epub()
cover_md = os.path.join(src_dir, 'cover.md')

# ── Step 0: Pandoc availability check ────────────────────────────────────
pandoc = shutil.which('pandoc')
if not pandoc:
    raise _errors.ToolError(
        "pandoc not found on PATH.\n"
        "Install it before running this script:\n"
        "  Windows :  winget install --id JohnMacFarlane.Pandoc -e\n"
        "             (or)  choco install pandoc\n"
        "  macOS   :  brew install pandoc\n"
        "  Debian  :  sudo apt install pandoc\n"
        "Then re-run:  python books/tools/to_epub.py"
    )
print(f"=== Step 0: pandoc detected at {pandoc} ===")
try:
    res = subprocess.run([pandoc, '--version'], capture_output=True, text=True, encoding='utf-8', check=False)
    first_line = (res.stdout or '').splitlines()[0] if res.stdout else ''
    if first_line:
        print(f"  {first_line}")
except (OSError, subprocess.SubprocessError) as exc:
    print(f"  pandoc version probe skipped: {exc}")

# ── Step 1: Ensure the merged Markdown is current ────────────────────────
print("\n=== Step 1: Ensuring merged Markdown is up to date ===")
rebuild = os.path.join(script_dir, 'merge.py')
if os.path.exists(rebuild):
    res = subprocess.run(
        [sys.executable, rebuild],
        capture_output=True, text=True, encoding='utf-8',
        cwd=repo_root,
    check=False,
    )
    if res.returncode != 0:
        raise _errors.ToolError(f"merge.py FAILED: {res.stderr}")
    last = (res.stdout or '').strip().splitlines()[-1] if res.stdout else ''
    if last:
        print(f"  {last}")

if not os.path.exists(merged_md):
    raise _errors.ToolError(f"Merged Markdown not found: {merged_md}")

# ── Step 2: Extract title / version / author from cover.md ───────────────
title = _config.project("display_title_en", _config.TITLE)
subtitle = _config.project("display_title_zh", _config.TITLE)
version = f'v{_config.VERSION}' if _config.VERSION else 'v1.0'
author = "其·龙（Stallman Wang）"
publish_date = datetime.date.today().isoformat()

if os.path.exists(cover_md):
    cover_text = _fsutil.read_text(cover_md)
    m = re.search(r'^# (.+?)$', cover_text, re.MULTILINE)
    if m:
        title = m.group(1).strip()
    m = re.search(r'^## (.+?)$', cover_text, re.MULTILINE)
    if m:
        subtitle = m.group(1).strip()
    m = re.search(r'版本 (v[\d.]+) · (\d{4}-\d{2}-\d{2})', cover_text)
    if m:
        # the cover only repeats the configured version; keep the configured one
        cover_version = m.group(1)
        if _config.VERSION and cover_version.lstrip('v') != _config.VERSION:
            print(f'  warn: cover says {cover_version}, book.toml says v{_config.VERSION}')
        publish_date = m.group(2)
    m = re.search(r'\*\*作者：([^*]+?)\*\*', cover_text)
    if m:
        author = m.group(1).strip()

# ── Step 3: Build a metadata YAML file for pandoc ────────────────────────
# Passed via ``--metadata-file`` so pandoc reads it as pure YAML rather
# than as a markdown YAML metadata block (the latter would require the
# ``yaml_metadata_block`` extension which we *disable* on the markdown
# reader, since the merged doc uses bare ``---`` as section separators).
publisher = _config.project("publisher", _config.TITLE)
description = _config.project("description", _config.TITLE)
metadata_yaml = textwrap.dedent(f"""\
    title: "{title}"
    subtitle: "{subtitle}"
    author: "{author}"
    date: "{publish_date}"
    rights: "© {publish_date.split('-')[0]} {author}"
    lang: zh-CN
    publisher: "{publisher}"
    description: "{description} — {version}"
    """)

metadata_path = os.path.join(dist_dir, '_epub_metadata.yaml')
_fsutil.write_text(metadata_path, metadata_yaml)

# ── Step 4: Build a small CSS sheet for typography ───────────────────────
# Reading apps already render their own fonts, so we keep this minimal:
# tighter ASCII art, sensible heading rhythm, code-block contrast.
EPUB_CSS = '/* ' + _config.project('running_head', _config.TITLE) + ' — EPUB stylesheet */' + """
body { line-height: 1.55; font-family: __FONT_SERIF__; }
h1 { font-size: 1.6em; margin-top: 1.2em; page-break-before: always; color: #1565C0; }
h2 { font-size: 1.3em; margin-top: 1em; color: #1565C0; }
h3 { font-size: 1.1em; margin-top: 0.8em; color: #1976D2; }
h4 { font-size: 1em; margin-top: 0.6em; color: #455A64; }

pre, code {
    font-family: __FONT_MONO__;
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

# the shared type scale decides sizes and rhythm; the paged dimensions stay in the
# PDF renderer, because an EPUB has no page to place them on
_layout_obj, _layout_problems = _layout.Layout.from_mapping(_config.THRESHOLDS)
for _problem in _layout_problems:
    print(f"  layout: {_problem}")
# the reader's device renders this, not this machine: the stylesheet declares
# portable families and embeds nothing, which is the opposite rule from the PDF
EPUB_CSS_SCALED = (_layout_obj.typescale().apply(EPUB_CSS)
                   .replace('__FONT_SERIF__', fonts.portable_stack('serif'))
                   .replace('__FONT_MONO__', fonts.portable_stack('mono')))
css_path = os.path.join(dist_dir, '_epub.css')
_fsutil.write_text(css_path, EPUB_CSS_SCALED)



# Two markdown rules decide where pandoc's `--split-level=1` cuts a chapter, and
# both are easy to violate by accident in a generated document:
#
#   1. an ATX heading needs a blank line before it — a `# 第11章` glued under a
#      list item is read as list continuation, so that chapter never starts a file;
#   2. a `====` run under a line makes it a setext H1 — captions written as a bold
#      line with a decorative underline therefore cut a chapter in half.
#
# Both are fixed generically here: no book-specific text, only the conventions.
ATX_HEADING = re.compile(r'^#{1,6}[ \t]+')
UNDERLINE = re.compile(r'^[ \t]*={3,}[ \t]*$')
SHORT_BOLD = re.compile(r'^[ \t]*(?:\*\*|__)[^*_]{1,120}(?:\*\*|__)[ \t]*$')
# a caption names a numbered figure or table — the same convention in every book
CAPTION_TEXT = re.compile(
    r'^[ \t]*\**\s*(?:图|表|Figure|Fig\.|Table)[ \t]*[\dA-Za-z]+[ \t]*[-–—.:：]', re.I)


def _is_caption(line: str) -> bool:
    return bool(SHORT_BOLD.match(line) or CAPTION_TEXT.match(line))


def normalise_headings(text: str) -> tuple[str, dict]:
    """Blank-line before ATX headings, drop decorative underlines under captions."""
    out: list[str] = []
    spaced = dropped = 0
    for line in text.splitlines():
        if UNDERLINE.match(line) and out and _is_caption(out[-1]):
            # the caption stays as a bold paragraph; only its underline goes, so
            # pandoc stops reading it as a setext H1
            dropped += 1
            continue
        if ATX_HEADING.match(line) and out and out[-1].strip():
            out.append('')
            spaced += 1
        out.append(line)
    return '\n'.join(out), {'spaced': spaced, 'dropped': dropped}


# ── Step 5: Run pandoc ───────────────────────────────────────────────────
# normalised copy, never the merged artifact: other gates compare that file with
# the manuscript line count, so it must keep the renderer's own output
_epub_text, _fixes = normalise_headings(_fsutil.read_text(merged_md))
# scratch, not dist: the normalised copy is an input to pandoc, not a deliverable,
# and a name derived from the merged file left a second .md in dist/
epub_src = os.path.join(_config.tmp_dir(), 'epub-source.md')
try:
    os.makedirs(_config.tmp_dir(), exist_ok=True)  # a minimal book need not have one
except OSError as exc:
    raise _errors.ToolError(f'error: cannot create {_config.tmp_dir()}: {exc}') from exc
_fsutil.write_text(epub_src, _epub_text)
print(f"  Headings normalised: {_fixes['spaced']} missing blank line(s), "
      f"{_fixes['dropped']} decorative underline(s)")

print(f"\n=== Step 2: Converting {merged_md} -> EPUB ===")

cmd = [
    pandoc,
    epub_src,
    '-o', epub_out,
    # Disable yaml_metadata_block in the input reader. The merged doc uses
    # bare `---` thematic-break lines as section separators, and pandoc's
    # default markdown reader treats those as the *start* of a YAML metadata
    # block, then fails parsing the body that follows. Metadata comes from
    # the standalone --metadata-file below, so we don't need inline YAML.
    '--from=markdown+pipe_tables+fenced_code_blocks+backtick_code_blocks-yaml_metadata_block',
    f'--metadata-file={metadata_path}',
    '--to=epub3',
    '--toc',
    '--toc-depth=3',
    '--split-level=1',  # one H1 per chapter file inside the EPUB
    f'--css={css_path}',
    '--metadata=lang:zh-CN',
]

print("  Command: pandoc <metadata> <merged.md> -o <epub>")
print("           --toc --toc-depth=3 --split-level=1 --to=epub3")

try:
    res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', check=False)
    if res.returncode != 0:
        detail = '\n'.join(part for part in (res.stdout, res.stderr) if part)
        raise _errors.ToolError(f"pandoc FAILED:\n{detail}" if detail
                                else "pandoc FAILED")
    if res.stdout.strip():
        for line in res.stdout.splitlines():
            print(f"  {line}")
    if res.stderr.strip():
        # pandoc warnings go to stderr but are not fatal; surface them.
        for line in res.stderr.splitlines():
            print(f"  [pandoc warn] {line}")
except FileNotFoundError:
    raise _errors.ToolError(
        "pandoc executable disappeared between detection and invocation.") from None
finally:
    # Tidy up the staging files; pandoc has already consumed them.
    for p in (metadata_path, css_path, epub_src):
        with contextlib.suppress(OSError):
            os.remove(p)

# ── Step 6: Report ───────────────────────────────────────────────────────
if not os.path.exists(epub_out):
    raise _errors.ToolError(f"EPUB not produced at {epub_out}")

size = os.path.getsize(epub_out)
print("\n=== Done ===")
print(f"EPUB:    {epub_out}")
print(f"Size:    {size:,} bytes ({size / 1024 / 1024:.2f} MB)")
print(f"Title:   {title}")
print(f"Version: {version}")
print(f"Author:  {author}")
print("Validate with epubcheck (optional):")
print(f"    java -jar epubcheck.jar {os.path.basename(epub_out)}")
