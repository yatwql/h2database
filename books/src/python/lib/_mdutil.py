#!/usr/bin/env python3
"""Markdown helpers shared by the HTML generator and the link audit.

Keeping the anchor algorithm in one place is what makes ``to_html``'s
``<h2 id="...">`` and ``_audit_links``'s anchor check agree.
"""

from __future__ import annotations

import functools
import re

from lib import _config

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^\s*```")
_SLUG_STRIP_RE = re.compile(r"[^\w\u4e00-\u9fff\u3400-\u4dbf\s-]")
HTML_HEADING_RE = re.compile(r'<h([1-4])\s+id="([^"]*)"[^>]*>(.*?)</h\1>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

LINK_RE = re.compile(r'!?\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')

EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "tel:", "data:", "ftp://")

# Figure captions are written `**图 X-Y: 标题**`. The shape lives here so the six
# audits that read captions cannot drift apart: structure (numbering), figures
# (counts), captions (wording), figure_clusters (bridges), smart (coverage),
# readability (metrics) all build from these names.
FIGURE_LABEL = "图"
FIGURE_ID = r"[A-Z0-9]+-\d+[a-z]*"
CHAPTER_FIGURE = r"(\d+)-(\d+[a-z]*)"
APPENDIX_FIGURE = r"([A-Z])-(\d+[a-z]*)"
FIGURE_CAPTION_RE = re.compile(rf"^\*\*{FIGURE_LABEL} ({FIGURE_ID}):\s*(.+?)\*\*\s*$")
FIGURE_PREFIX_RE = re.compile(rf"^\*\*{FIGURE_LABEL} {FIGURE_ID}:")
# The same prefix, scanned across a whole document: the counters work on the file,
# the caption audits work on one line, so both shapes come from one definition.
FIGURE_LINE_RE = re.compile(FIGURE_PREFIX_RE.pattern, re.MULTILINE)
FIGURE_LINE_UNBOLD_RE = re.compile(rf"^{FIGURE_LABEL} {FIGURE_ID}:", re.MULTILINE)


# Source coordinates are written `Widget.java:12`. The shape lives here for the
# same reason the figure shape does: the counters in cover, balance, book_quality,
# prose_quality and smart must not each keep matching one hard-coded suffix.
@functools.lru_cache(maxsize=8)
def source_ref_re(suffixes: tuple[str, ...]) -> re.Pattern[str]:
    """`Class.java:12` shaped references, for the suffixes a book declares.

    Built from the configured suffixes rather than a literal: a gate must not
    keep counting `.java:` after the analysed tree became C or Rust.
    """
    return re.compile(r"\b(\w+)(?:" + "|".join(re.escape(x) for x in suffixes) + r"):(\d+)")


EXCERPT_ELISION_RE = re.compile(r"^(?://|#|--)?\s*(\.\.\.|…)$")


def excerpt_is_elision(line: str) -> bool:
    """Whether a line marks skipped source: `...`, `// ...`, `# …`."""
    return bool(EXCERPT_ELISION_RE.match(line.strip()))


def excerpt_code(line: str) -> str:
    """The code part of a line: everything before an appended `//` annotation."""
    return line.split("//", 1)[0].rstrip()


def excerpt_line_matches(shown: str, source: str) -> bool:
    """Equal as code; a blank line matches a blank line; an elision matches anything.

    The book explains a line by appending a comment to it and marks omissions with `...`;
    neither is a change. A different identifier, literal or statement is.
    """
    if excerpt_is_elision(shown) or shown.strip() == source.strip():
        return True
    return excerpt_code(shown).strip() == excerpt_code(source).strip()


def excerpt_span_matches(body: list[str], source: list[str]) -> bool:
    """Exact line-for-line, or an in-order subsequence when the body declares elisions."""
    if any(excerpt_is_elision(line) for line in body):
        cursor = 0
        for shown in body:
            if excerpt_is_elision(shown):
                continue
            while cursor < len(source) and not excerpt_line_matches(shown, source[cursor]):
                cursor += 1
            if cursor == len(source):
                return False
            cursor += 1
        return True
    return len(body) == len(source) and all(
        excerpt_line_matches(shown, real) for shown, real in zip(body, source, strict=False))


def coord_count(text: str) -> int:
    """Source coordinates in the text, for the suffixes this book declares."""
    return len(source_ref_re(tuple(_config.source_suffixes())).findall(text))


def table(headers: list[str], rows: list[list[str]], cap: int = 20) -> list[str]:
    """Markdown table lines: header, separator, then at most ``cap`` rows."""
    kept = rows[:cap]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in kept]
    return out


def figure_caption(line: str) -> tuple[str, str] | None:
    """(figure id, title) for a caption line, or None when it is not one.

    Public API: the gates parse captions with `FIGURE_*` shapes directly for speed,
    but any caller that wants the id and the title in one step comes here — so the
    rule about what counts as a caption stays in one place.
    """
    match = FIGURE_CAPTION_RE.match(line.strip())
    return (match.group(1), match.group(2).strip()) if match else None


def slugify(title: str) -> str:
    """GitHub-style heading anchor, matching what to_html emits."""
    anchor = title.strip().lower()
    anchor = _SLUG_STRIP_RE.sub("", anchor)
    return anchor.replace(" ", "-")


def plain_text(fragment: str) -> str:
    """Inline HTML -> text (tags removed, zero-width space dropped)."""
    return _TAG_RE.sub("", fragment).replace("\u200b", "").strip()


def html_headings(html: str) -> list[dict]:
    """Every ``<hN id="...">`` in document order as {index, level, id, text}.

    One parser for the PDF pipeline (print, outline, verification), so heading
    order and text can never drift between those steps.
    """
    return [
        {
            "index": index,
            "level": int(match.group(1)),
            "id": match.group(2),
            "text": plain_text(match.group(3)),
        }
        for index, match in enumerate(HTML_HEADING_RE.finditer(html))
    ]


def iter_headings(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return (level, title, slug) for every heading outside fenced blocks."""
    out: list[tuple[int, str, str]] = []
    in_fence = False
    for raw in lines:
        if _FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(raw.rstrip("\n"))
        if m:
            title = m.group(2).strip()
            out.append((len(m.group(1)), title, slugify(title)))
    return out


def heading_slugs(lines: list[str]) -> set[str]:
    return {slug for _level, _title, slug in iter_headings(lines)}


def is_external(target: str) -> bool:
    lowered = target.strip().lower()
    return lowered.startswith(EXTERNAL_SCHEMES)


def iter_links(text: str) -> list[tuple[str, str]]:
    """Return (label, target) for every inline link/image in ``text``."""
    return [(m.group(1), m.group(2)) for m in LINK_RE.finditer(text)]


def split_fences(text: str) -> list[str]:
    """Split text into (non-fenced) chunks, dropping fenced code blocks."""
    chunks: list[str] = []
    current: list[str] = []
    in_fence = False
    for raw in text.split("\n"):
        if _FENCE_RE.match(raw):
            in_fence = not in_fence
            if not in_fence:
                current.append("")
            continue
        if not in_fence:
            current.append(raw)
    if current:
        chunks.append("\n".join(current))
    return chunks


_CJK_RANGE = r"\u4e00-\u9fff"
# zero-width assertions so back-to-back boundaries all get a space
_CJK_LATIN = re.compile(f"(?<=[{_CJK_RANGE}])(?=[A-Za-z0-9])|(?<=[A-Za-z0-9])(?=[{_CJK_RANGE}])")
# Chinese numbering and reference idioms stay tight: 第3章 / §6.2 / 图 6-12 / 附录 A
_IDIOM = re.compile(
    r"第\d+[章节题条个张]|§\d+(?:\.\d+)*|图 [A-Z0-9]+-\d+|表 [A-Z0-9]+-\d+|附录 [A-Z]"
)


def _space_plain(part: str) -> str:
    """Insert CJK/Latin spaces in one non-code segment, protecting idioms."""
    masks: list[str] = []

    def mask(match: re.Match) -> str:
        masks.append(match.group(0))
        return f"\x00{len(masks) - 1}\x00"

    part = _IDIOM.sub(mask, part)
    part = _CJK_LATIN.sub(" ", part)
    return re.sub(r"\x00(\d+)\x00", lambda m: masks[int(m.group(1))], part)


def space_cjk_latin(text: str) -> str:
    """Insert a space between CJK characters and Latin letters/digits.

    Inline code spans (``...``) and links (``[label](target)``) are left
    untouched, and Chinese numbering idioms (第3章 / §6.2 / 图 6-12) stay tight.
    """
    parts = re.split(r"(`[^`]*`)", text)
    out = []
    for index, part in enumerate(parts):
        if index % 2 == 1:  # inside a code span
            out.append(part)
            continue
        part = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", lambda m: f"[{m.group(1)}]({m.group(2)})", part)
        out.append(_space_plain(part))
    return "".join(out)
