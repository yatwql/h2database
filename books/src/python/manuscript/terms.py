#!/usr/bin/env python3
"""
Add glossary reference note to each chapter's guide block.

Inserts a standardized line into each chapter's existing guide block
(> **本章导读** section) referencing the book-end glossary.

Modes:
  (default) Insert glossary reference into unannotated chapter files.
  --report-missing  Scan chapter files for bold terms not in glossary.
  --check           Like --report-missing, but exits with code 1 if any missing.
  --check-related   Verify [[term]] cross-refs in glossary.md all resolve.
                    Exits with code 1 if any dangling links found.
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import functools
import glob
import os
import re
import sys

from lib import _config, _errors, _fsutil

_fsutil.pin_stdout_utf8()

docs_dir = _config.BOOK_ROOT
src_dir = _config.MANUSCRIPT_DIR
dist_dir = _config.DIST_DIR


def _lang_terms() -> dict:
    """The active book's language pack, read when asked.

    Read through the book rather than captured at import: one process may serve
    more than one book, and a module-level copy would keep answering for the
    first one.
    """
    return _config.language().get("terms") or {}


def reference_line() -> str:
    return _lang_terms().get("reference_line", "术语参考")


def glossary_title() -> str:
    return _lang_terms().get("glossary_title", "术语表")


def glossary_link() -> str:
    return _lang_terms().get("glossary_link", "back/glossary.md")


glossary_path = os.path.join(src_dir, glossary_link())


def _write_text(path: str, text: str) -> None:
    """Write a UTF-8 text file, failing with a clean message on I/O error."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        raise _errors.ToolError(f"error: cannot write {path}: {exc}") from exc


def parse_glossary_terms(path: str) -> dict[str, list[int]]:
    """Parse glossary.md and return a mapping of term names to chapter numbers.

    Supports the multi-line entry format:
        - **Term**: 释义第一行
          释义第二行
          **章节**：第N章 §X.Y
          **相关**：[[Other]]、[[Another]]

    Falls back gracefully on single-line entries.
    """
    terms: dict[str, list[int]] = {}
    term_pattern = re.compile(r"^- \*\*([^*]+)\*\*")
    ch_pattern = re.compile(r"第(\d+)章")

    lines = _fsutil.read_lines(path)

    current_term: str | None = None
    current_chapters: list[int] = []
    for line in lines:
        m = term_pattern.match(line.strip())
        if m:
            # Flush previous term
            if current_term is not None:
                terms[current_term] = current_chapters
            current_term = m.group(1).strip()
            # Collect chapters from the same line (single-line format)
            current_chapters = [int(c) for c in ch_pattern.findall(line)]
        elif current_term is not None:
            # Continuation line of a multi-line entry
            for c in ch_pattern.findall(line):
                ch = int(c)
                if ch not in current_chapters:
                    current_chapters.append(ch)
            # Top-level non-list-item line ends the entry
            if line and not line[0].isspace() and not line.startswith("-"):
                terms[current_term] = current_chapters
                current_term = None
                current_chapters = []

    # Flush trailing term
    if current_term is not None:
        terms[current_term] = current_chapters

    return terms


def parse_glossary_with_related(path: str) -> dict[str, dict]:
    """Parse glossary.md into rich entries: {term: {chapters, related, body}}.

    Used by --check-related to verify see-also closure.
    """
    entries: dict[str, dict] = {}
    term_pattern = re.compile(r"^- \*\*([^*]+)\*\*")
    ch_pattern = re.compile(r"第(\d+)章")
    # see-also links use [[Term]] markdown-flavored cross references
    related_pattern = re.compile(r"\[\[([^\]]+)\]\]")

    lines = _fsutil.read_lines(path)

    current: dict | None = None
    current_term: str | None = None
    for raw in lines:
        line = raw.rstrip("\n")
        # Boundary: horizontal rule or italic footer terminates open entry
        stripped = line.strip()
        if stripped.startswith(("---", "## ")):
            if current_term is not None and current is not None:
                entries[current_term] = current
                current_term = None
                current = None
            continue
        m = term_pattern.match(line.strip())
        if m:
            if current_term is not None and current is not None:
                entries[current_term] = current
            current_term = m.group(1).strip()
            current = {"chapters": [], "related": [], "body": []}
            for c in ch_pattern.findall(line):
                ch = int(c)
                if ch not in current["chapters"]:
                    current["chapters"].append(ch)
        elif current is not None and current_term is not None:
            # Continuation line; the term is set exactly when the entry is
            current["body"].append(line)
            for c in ch_pattern.findall(line):
                ch = int(c)
                if ch not in current["chapters"]:
                    current["chapters"].append(ch)
            for r in related_pattern.findall(line):
                r = r.strip()
                if r and r not in current["related"]:
                    current["related"].append(r)
            if line and not line.startswith(" ") and not line.startswith("-"):
                # Top-level non-indented line — end of entry. The pair is never
                # half-set, so the key is always there.
                entries[current_term] = current
                current_term = None
                current = None

    if current_term is not None and current is not None:
        entries[current_term] = current

    return entries


def check_related(verbose: bool = False) -> int:
    """Verify see-also closure: every [[Term]] link must resolve to an existing entry.

    Returns count of dangling references. Single-edge references (A->B without B->A)
    are reported but do not count as errors — they are common ("X uses Y" without
    "Y is used by X").
    """
    entries = parse_glossary_with_related(glossary_path)
    known = {t.lower() for t in entries}

    dangling = 0
    one_way = 0
    for term, info in entries.items():
        for r in info["related"]:
            r_norm = r.lower()
            if r_norm not in known:
                # Try a few common normalization fallbacks
                # e.g. "COW / Copy-on-Write" matches "COW" or "Copy-on-Write"
                hit = False
                for candidate in known:
                    if r_norm in candidate or candidate.startswith(r_norm + " "):
                        hit = True
                        break
                if not hit:
                    dangling += 1
                    if verbose:
                        print(f"  DANGLING: '{term}' -> [[{r}]]")

    if verbose:
        print(f"\nDangling see-also references: {dangling}")
        print(f"One-way see-also references: {one_way} (informational)")
    return dangling


# The book's own term tables — Chinese/English aliases and the phrases that are
# never glossary terms — live in `data/book/glossary.toml`. They are content, not
# toolchain: a C book shares none of these strings.
def glossary_config() -> str:
    """Where this book keeps its term aliases and its skip list."""
    return _config.book_path("glossary.toml")


@functools.lru_cache(maxsize=1)
def _book_terms() -> tuple[dict[str, str], frozenset[str]]:
    """(aliases, skip) from the book's glossary file, empty when it has none."""
    import tomllib

    try:
        with open(glossary_config(), "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}, frozenset()
    aliases = {str(key): str(value) for key, value in (data.get("aliases") or {}).items()}
    return aliases, frozenset(str(item) for item in (data.get("skip") or []))


def term_aliases() -> dict[str, str]:
    """Chinese term → the English name the glossary is filed under."""
    return _book_terms()[0]


def skip_terms() -> frozenset[str]:
    """Phrases that look like terms (headings, feature names) and are not."""
    return _book_terms()[1]


def is_glossary_candidate(term: str) -> bool:
    """Return True if this bold term could be a glossary candidate (vs. heading/noise)."""
    if len(term) < 3:
        return False
    # Contains structural function words (phrases, not terms)
    if re.search(r"[的与和及或]", term):
        return False  # Ends with 层 (layer reference)
    if term.endswith("层"):
        return False
    # Starts with a phase marker
    if re.match(r"^第[一二三四五六七八九十\d]", term):
        return False
    # Contains 详解/追踪/练习/场景
    if re.search(r"(详解|追踪|练习|场景)", term):
        return False
    # Method names (contain parentheses)
    if "()" in term:
        return False
    # Arrow operators (state transitions)
    if "→" in term:
        return False
    # Code/comparison operators
    if "->" in term:
        return False
    # Ends with Chinese colon or English colon (heading style)
    if re.search(r"[：:]$", term):
        return False
    # Pure Chinese with 4+ characters (likely a descriptive heading)
    if re.match(r'^[一-鿿\s，。、；：""' "（）()]+$", term) and len(term) >= 4:
        return False
    # Contains file path patterns or code references (for the suffixes this book
    # declares, so a C book's `foo.c` is filtered as well as a Java one's `Foo.java`)
    if re.search(r"[/\\]", term) or any(suffix in term for suffix in _config.source_suffixes()):
        return False
    # Backtick-containing terms (code references)
    if "`" in term:
        return False
    # Parenthesized descriptions (e.g. "DML（数据操作语言）")
    if re.match(r".+[（(][^）)]+[）)]", term):
        return False
    # Too long to be a single term
    if len(term) > 35:
        return False
    # Version strings
    if re.match(r"^v?\d+[\.x]\d+", term):
        return False
    # Pure English single words shorter than 8 chars (common like Plan, Select)
    if re.match(r"^[A-Z][a-zA-Z]{1,7}$", term):
        return False
    # Method call patterns (name followed by parentheses content)
    if re.match(r"^[a-z]\w+\(", term):
        return False
    # SQL keywords or tips
    if re.match(r"^(SELECT|INSERT|UPDATE|DELETE|JOIN|FROM|WHERE)\s", term):
        return False
    # Descriptive phrases like "每次 put() 导致页面超出容量"
    return not re.match(r"^(每次|当|如果|所有|使用)", term)


def report_missing(check_mode: bool = False) -> int:
    """Scan chapter files for bold terms not found in glossary.

    Returns count of missing term occurrences (not unique terms).
    Exits with code 1 in --check mode if any missing terms found.
    """
    terms = parse_glossary_terms(glossary_path)
    # Build normalized lookup: lowercase + strip common suffixes
    known_normalized: dict[str, str] = {}
    # Also build Chinese alias lookup for cross-language matching
    chinese_aliases: dict[str, str] = {}
    # Known Chinese<->English term mappings
    for t in terms:
        known_normalized[t.lower().rstrip(".")] = t
        # Check if this term has Chinese aliases
        for ch, en in term_aliases().items():
            if en.lower() == t.lower() or t.lower().startswith(en.lower()):
                chinese_aliases[ch] = t
                # Also add normalized version
                known_normalized[ch.lower()] = t

    chapter_files = sorted(glob.glob(os.path.join(src_dir, "ch[0-9]*.md")))

    # Patterns for term-like text in chapter files
    bold_pattern = re.compile(r"\*\*([^*]+)\*\*")

    # Structural markers that should never be glossary terms

    missing_count = 0
    for fpath in chapter_files:
        fname = os.path.basename(fpath)
        lines = _fsutil.read_lines(fpath)

        for lineno, line in enumerate(lines, start=1):
            # Extract bold terms
            for m in bold_pattern.finditer(line):
                term = m.group(1).strip()
                if not is_glossary_candidate(term):
                    continue
                # Skip figure captions, section numbers
                if re.match(r"^图 \d+-\d+", term) or re.match(r"^\d+[.、]", term):
                    continue
                # Skip explicit skip terms
                if term in skip_terms():
                    continue

                norm = term.lower().rstrip(".")
                if norm not in known_normalized:
                    print(f"  MISSING: {fname}:{lineno}: **{term}**")
                    missing_count += 1

    if check_mode and missing_count > 0:
        raise _errors.ToolError(
            f"Found {missing_count} missing term(s). Use --report-missing for details."
        )

    return missing_count


# ---- Entry point ----


def main(argv: list[str]) -> int:
    """CLI entry point. Import-safe: nothing runs at module import time."""
    if "--check-related" in argv:
        return 1 if check_related(verbose=True) > 0 else 0

    if "--report-missing" in argv:
        count = report_missing(check_mode=False)
        print(f"\nTotal missing term occurrences: {count}")
        return 0

    if "--check" in argv:
        count = report_missing(check_mode=True)
        print(f"\nNo missing terms found (checked {count} occurrences).")
        return 0

    # Default: insert the glossary reference into unannotated chapters.
    chapter_files = sorted(glob.glob(os.path.join(src_dir, "ch[0-9]*.md")))
    glossary_ref = (
        f"> **{reference_line()}**: 本章涉及的专业术语详见书末"
        f"[{glossary_title()}]({glossary_link()})。\n"
    )
    count = 0

    for fpath in chapter_files:
        content = _fsutil.read_text(fpath)

        if "术语参考" in content:
            print(f"  Already annotated: {os.path.basename(fpath)}")
            continue

        lines = content.split("\n")
        last_guide_line = -1
        in_guide = False
        for i, line in enumerate(lines):
            if line.strip().startswith("> **本章导读**"):
                in_guide = True
            if in_guide and line.strip().startswith(">"):
                last_guide_line = i
            elif in_guide and not line.strip().startswith(">") and line.strip() != "":
                break

        if last_guide_line >= 0:
            lines.insert(last_guide_line + 1, glossary_ref.rstrip("\n"))
            content = "\n".join(lines)
            _write_text(fpath, content)
            count += 1
            print(f"  Added to {os.path.basename(fpath)}")
        else:
            print(f"  No guide block found: {os.path.basename(fpath)}")

    print(f"Updated {count} chapter files")
    return 0


if __name__ == "__main__":
    sys.exit(_errors.run(main, sys.argv[1:]))
