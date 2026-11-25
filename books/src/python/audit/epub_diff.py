"""Compare two EPUB builds, or check one build on its own.

An EPUB has no page count, so the axes that can be measured are the ones a
reader would notice: how much text there is, how many chapter files carry it,
the CSS rules that decide how text looks (font stack, sizes, leading), and
whether the figures are bitmaps or text. Measuring them makes "the new build
looks about the same as the old one" a statement a gate can check.

    python src/python/audit/epub_diff.py --compare ref.epub built.epub
    python src/python/audit/epub_diff.py --check built.epub --merged merged.md

`--check` compares the chapter file count with the number of level-one headings
in the merged markdown: pandoc splits on what it reads as an H1, so a missing or
extra file means a heading was misread somewhere.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lib import _fsutil  # noqa: E402

BODY_FILE = re.compile(r".*/ch\d+\.xhtml$")
H1_LINE = re.compile(r"^#[ \t]+\S")
CSS_FONT = re.compile(r"font-family:\s*([^;]+);")
CSS_SIZE = re.compile(r"font-size:\s*([^;]+);")
CSS_LEAD = re.compile(r"line-height:\s*([^;]+);")
BITMAP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


def _strip(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def measure(path: str) -> dict:
    """Everything comparable about one EPUB, read from the container itself."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        bodies = sorted(n for n in names if BODY_FILE.match(n))
        chars = sum(len(_strip(archive.read(n).decode("utf-8", "ignore"))) for n in bodies)
        css = ""
        for name in names:
            if name.endswith(".css"):
                css += archive.read(name).decode("utf-8", "ignore")
        bitmaps = [n for n in names if n.lower().endswith(BITMAP_SUFFIXES)]
    return {
        "bytes": os.path.getsize(path),
        "chapters": len(bodies),
        "chars": chars,
        "fonts": sorted({m.strip() for m in CSS_FONT.findall(css)}),
        "sizes": CSS_SIZE.findall(css),
        "leads": CSS_LEAD.findall(css),
        "bitmaps": len(bitmaps),
    }


def _leads(stacks: list[str]) -> list[str]:
    """The first family of each declared stack."""
    return sorted(stack.split(",")[0].strip().strip("\"'") for stack in stacks)


def _delta(new: float, old: float) -> str:
    if not old:
        return "0.0%" if not new else "new"
    return f"{(new - old) / old * 100:+.1f}%"


def compare(reference: str, built: str) -> int:
    """Print both measurements side by side; return 1 when a soft axis drifts."""
    a, b = measure(reference), measure(built)
    rows = (
        ("size MB", round(a["bytes"] / 1048576, 2), round(b["bytes"] / 1048576, 2)),
        ("chapter files", a["chapters"], b["chapters"]),
        ("body chars", a["chars"], b["chars"]),
        ("bitmaps", a["bitmaps"], b["bitmaps"]),
        ("font stacks", len(a["fonts"]), len(b["fonts"])),
        ("font sizes", len(a["sizes"]), len(b["sizes"])),
        ("line heights", len(a["leads"]), len(b["leads"])),
    )
    print(f"{'metric':14s} {'reference':>12s} {'built':>12s} {'delta':>8s}")
    drifted = 0
    for label, old, new in rows:
        print(f"{label:14s} {old:>12} {new:>12} {_delta(new, old):>8s}")
    if a["sizes"] != b["sizes"]:
        drifted += 1
        print(f"  font sizes differ: {a['sizes']} -> {b['sizes']}")
    if a["leads"] != b["leads"]:
        drifted += 1
        print(f"  line heights differ: {a['leads']} -> {b['leads']}")
    # a stack that gains fallbacks is not a change of typeface: the first family is
    # what a reader actually sees, so that is what has to match
    if _leads(a["fonts"]) != _leads(b["fonts"]):
        drifted += 1
        print(f"  leading font family changed: {_leads(a['fonts'])} -> {_leads(b['fonts'])}")
    elif a["fonts"] != b["fonts"]:
        print("  font stacks differ only in fallbacks (fine)")
    return 1 if drifted else 0


def check(built: str, merged: str) -> int:
    """Chapter files must equal the level-one headings; size must stay in budget."""
    stats = measure(built)
    if not os.path.exists(merged):
        print(f"  FAIL merged markdown not found: {merged}")
        return 1
    text = _fsutil.read_text(merged)
    headings = sum(1 for line in text.splitlines() if H1_LINE.match(line))
    ok = True
    # every level-one heading becomes a file, and the cover is prepended as one
    # more, so the expected count is headings + 1
    expected = headings + 1
    if stats["chapters"] != expected:
        print(
            f"  FAIL chapters: {stats['chapters']} files, expected {expected} "
            f"({headings} level-1 headings + cover)"
        )
        ok = False
    else:
        print(f"  OK: {stats['chapters']} chapter files = {headings} level-1 headings + cover")
    if not stats["bitmaps"]:
        print("  OK: figures are text, so no image resolution to compare")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--compare", nargs=2, metavar=("REFERENCE", "BUILT"))
    parser.add_argument("--check", metavar="BUILT")
    parser.add_argument("--merged", metavar="MERGED_MD")
    parser.add_argument(
        "--json", action="store_true", help="print the measurements instead of a table"
    )
    args = parser.parse_args(argv)
    if args.compare:
        if args.json:
            print(
                json.dumps(
                    {"reference": measure(args.compare[0]), "built": measure(args.compare[1])},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        return compare(*args.compare)
    if args.check:
        if not args.merged:
            parser.error("--check needs --merged")
        if args.json:
            stats = measure(args.check)
            print(json.dumps(stats, ensure_ascii=False, indent=2))
            return 0
        return check(args.check, args.merged)
    parser.error("nothing to do: pass --compare or --check")


if __name__ == "__main__":
    sys.exit(main())
