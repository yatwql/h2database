#!/usr/bin/env python3
"""Markdown fixes an EPUB needs before pandoc splits it into chapter files.

Pandoc decides chapter boundaries by what it reads as a level-one heading, and two
Markdown conventions defeat that:

  1. an ATX heading written directly under a list item or paragraph without a blank
     line continues that block, so it never opens a new file;
  2. a `====` run under a line makes that line a setext H1, so a caption written as a
     bold line with a decorative underline cuts a chapter in half.

Both are fixed generically here — no book-specific text, only the conventions — and the
module imports nothing heavy, so the rules can be tested without running pandoc.
"""
from __future__ import annotations

import re

ATX_HEADING = re.compile(r'^#{1,6}[ \t]+')
UNDERLINE = re.compile(r'^[ \t]*={3,}[ \t]*$')
SHORT_BOLD = re.compile(r'^[ \t]*(?:\*\*|__)[^*_]{1,120}(?:\*\*|__)[ \t]*$')
# a caption names a numbered figure or table — the same convention in every book
CAPTION_TEXT = re.compile(
    r'^[ \t]*\**\s*(?:图|表|Figure|Fig\.|Table)[ \t]*[\dA-Za-z]+[ \t]*[-–—.:：]', re.I)


def is_caption(line: str) -> bool:
    """True for a short bold line or a line that names a numbered figure/table."""
    return bool(SHORT_BOLD.match(line) or CAPTION_TEXT.match(line))


def normalise_headings(text: str) -> tuple[str, dict]:
    """Blank-line before ATX headings, drop decorative underlines under captions.

    Returns the rewritten text and what was changed, so the caller can report
    `spaced` and `dropped` instead of silently reshaping the document.
    """
    out: list[str] = []
    spaced = dropped = 0
    for line in text.splitlines():
        if UNDERLINE.match(line) and out and is_caption(out[-1]):
            # the caption stays as a bold paragraph; only its underline goes, so
            # pandoc stops reading it as a setext H1
            dropped += 1
            continue
        if ATX_HEADING.match(line) and out and out[-1].strip():
            out.append('')
            spaced += 1
        out.append(line)
    return '\n'.join(out), {'spaced': spaced, 'dropped': dropped}
